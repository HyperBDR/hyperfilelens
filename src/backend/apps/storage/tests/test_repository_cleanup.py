from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.node.models import Node
from apps.storage.repositories.models import (
    Repository,
    RepositoryTask,
    RepositoryUsageShard,
)
from apps.storage.services.internal.repository_cleanup import (
    create_direct_nas_target_cleanup_task,
    create_repository_cleanup_task,
    direct_nas_cleanup_target_ids,
    repository_cleanup_preflight,
    run_repository_cleanup_task,
)
from apps.task.models import Task, TaskResource
from apps.task.services.interface import create_task


class RepositoryCleanupTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            key="repository-cleanup-org",
            name="Repository Cleanup Org",
        )

    def _s3_repository(self, name: str = "cleanup-s3") -> Repository:
        return Repository.objects.create(
            organization_id=self.org.id,
            name=name,
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_platform=Repository.S3Platform.AWS,
            s3_bucket="cleanup-bucket",
            config={"prefix": "managed/repository/", "access_key_id": "test-key"},
        )

    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        return_value={"physical_cleanup": "deleted"},
    )
    def test_repository_cleanup_tombstones_and_duplicate_delivery_is_idempotent(
        self,
        execute_cleanup,
    ):
        repository = self._s3_repository()
        repository_task = create_repository_cleanup_task(
            repository=repository,
            dispatch=False,
        )

        self.assertEqual(
            repository_task.task.display_name,
            "Repository Cleanup · cleanup-s3",
        )

        result = run_repository_cleanup_task(repository_task_id=repository_task.id)
        duplicate_result = run_repository_cleanup_task(repository_task_id=repository_task.id)

        repository.refresh_from_db()
        repository_task.task.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(duplicate_result["physical_cleanup"], "deleted")
        self.assertEqual(repository_task.operation_type, RepositoryTask.OperationType.CLEANUP_REPOSITORY)
        self.assertEqual(repository.status, Repository.Status.REMOVED)
        self.assertEqual(repository.cleanup_result, Repository.CleanupResult.DELETED)
        self.assertIsNotNone(repository.removed_at)
        self.assertEqual(repository_task.task.status, Task.Status.SUCCESS)
        self.assertTrue(
            TaskResource.objects.filter(
                task=repository_task.task,
                resource_type=TaskResource.Type.REPOSITORY,
                resource_id=repository.id,
            ).exists()
        )
        execute_cleanup.assert_called_once()

    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._tombstone_repository",
        side_effect=RuntimeError("metadata finalize failed"),
    )
    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        return_value={"physical_cleanup": "deleted"},
    )
    def test_repository_cleanup_does_not_succeed_before_metadata_finalize(
        self,
        execute_cleanup,
        tombstone_repository,
    ):
        repository = self._s3_repository("metadata-finalize-s3")
        repository_task = create_repository_cleanup_task(repository=repository, dispatch=False)

        result = run_repository_cleanup_task(repository_task_id=repository_task.id)

        repository.refresh_from_db()
        repository_task.task.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(repository_task.task.status, Task.Status.FAILED)
        self.assertEqual(repository.status, Repository.Status.REMOVE_FAILED)
        execute_cleanup.assert_called_once()
        tombstone_repository.assert_called_once()

    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        side_effect=RuntimeError("owner offline"),
    )
    def test_force_cleanup_can_be_selected_initially_and_skips_physical_delete(
        self,
        execute_cleanup,
    ):
        repository = self._s3_repository("force-s3")
        forced_task = create_repository_cleanup_task(
            repository=repository,
            force=True,
            dispatch=False,
        )
        run_repository_cleanup_task(repository_task_id=forced_task.id)

        forced_task.task.refresh_from_db()
        repository.refresh_from_db()
        self.assertTrue(forced_task.force)
        self.assertEqual(forced_task.task.status, Task.Status.SUCCESS)
        self.assertEqual(repository.status, Repository.Status.REMOVED)
        self.assertEqual(repository.cleanup_result, Repository.CleanupResult.FORCE_SKIPPED)
        execute_cleanup.assert_not_called()

    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        side_effect=RuntimeError("owner offline"),
    )
    def test_remove_failed_repository_delete_creates_an_independent_task(self, execute_cleanup):
        repository = self._s3_repository("delete-again-s3")
        failed_task = create_repository_cleanup_task(repository=repository, dispatch=False)
        run_repository_cleanup_task(repository_task_id=failed_task.id)
        repository.refresh_from_db()

        next_task = create_repository_cleanup_task(repository=repository, dispatch=False)

        self.assertNotEqual(next_task.id, failed_task.id)
        self.assertFalse(next_task.force)
        self.assertEqual(next_task.task.trigger_type, Task.TriggerType.MANUAL)
        repository.refresh_from_db()
        self.assertEqual(repository.status, Repository.Status.REMOVING)
        execute_cleanup.assert_called_once()

    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        return_value={"physical_cleanup": "deleted"},
    )
    def test_direct_nas_target_tasks_are_independent_from_logical_cleanup(self, execute_cleanup):
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="direct-nas",
            repo_type=Repository.Type.NAS,
            nas_protocol=Repository.NasProtocol.NFS,
            status=Repository.Status.CREATED,
            health=Repository.Health.UNVERIFIED,
            config={"server_address": "10.0.0.1", "share_path": "/backups"},
        )
        nodes = []
        config_ids = []
        shards = []
        for index in range(2):
            node = Node.objects.create(
                organization=self.org,
                name=f"agent-{index}",
                role=Node.Role.AGENT,
                status=Node.Status.ONLINE,
                metadata={"inventory": {"capabilities": ["repository_cleanup_v1"]}},
            )
            nodes.append(node)
            config_id = index + 100
            config_ids.append(config_id)
            shards.append(
                RepositoryUsageShard.objects.create(
                    organization_id=self.org.id,
                    repository_id=repository.id,
                    node_id=node.id,
                    repository_subdir=f"hp-repos/agent-{node.id}",
                    source_config_count=1,
                    source_config_ids=[config_id],
                    status=RepositoryUsageShard.Status.SUCCESS,
                )
            )
        source_unregister = create_task(
            organization_id=self.org.id,
            task_type=Task.Type.SOURCE_UNREGISTER,
            display_name="Unregister Direct NAS source",
            resources=[],
            steps=["cleanup_direct_nas_repositories"],
        )

        preflight = repository_cleanup_preflight(repository=repository)
        self.assertFalse(preflight["allowed"])
        self.assertTrue(
            any(item["code"] == "active_physical_targets" for item in preflight["blockers"])
        )

        physical_tasks = []
        for index, (node, config_id) in enumerate(zip(nodes, config_ids, strict=True)):
            target_ids = direct_nas_cleanup_target_ids(
                repository=repository,
                backup_config_ids=[config_id],
                owner_node_id=node.id,
            )
            self.assertEqual(len(target_ids), 1)
            physical_task = create_direct_nas_target_cleanup_task(
                repository=repository,
                target_id=target_ids[0],
                triggered_by_task=source_unregister,
            )
            if index == 0:
                physical_task.task.status = Task.Status.FAILED
                physical_task.task.save(update_fields=["status", "updated_at"])
                failed_physical_task = physical_task
                same_attempt_task = create_direct_nas_target_cleanup_task(
                    repository=repository,
                    target_id=target_ids[0],
                    triggered_by_task=source_unregister,
                )
                self.assertEqual(same_attempt_task.id, failed_physical_task.id)
                source_unregister.retry_count += 1
                source_unregister.save(update_fields=["retry_count", "updated_at"])
                physical_task = create_direct_nas_target_cleanup_task(
                    repository=repository,
                    target_id=target_ids[0],
                    triggered_by_task=source_unregister,
                )
                self.assertNotEqual(physical_task.id, failed_physical_task.id)
                self.assertEqual(
                    physical_task.task.request_payload["source_unregister_attempt"],
                    1,
                )
            run_repository_cleanup_task(repository_task_id=physical_task.id)
            physical_tasks.append(physical_task)

        repository.refresh_from_db()
        for shard in shards:
            shard.refresh_from_db()
            self.assertFalse(shard.is_active)
        self.assertEqual(repository.status, Repository.Status.CREATED)
        self.assertEqual(
            {task.operation_type for task in physical_tasks},
            {RepositoryTask.OperationType.CLEANUP_TARGET},
        )
        self.assertEqual(
            {task.triggered_by_task_id for task in physical_tasks},
            {source_unregister.id},
        )

        logical_task = create_repository_cleanup_task(repository=repository, dispatch=False)
        self.assertEqual(logical_task.operation_type, RepositoryTask.OperationType.CLEANUP_REPOSITORY)
        self.assertIsNone(logical_task.execution_target_id)
        self.assertIsNone(logical_task.triggered_by_task_id)
        run_repository_cleanup_task(repository_task_id=logical_task.id)
        repository.refresh_from_db()
        self.assertEqual(repository.status, Repository.Status.REMOVED)
        self.assertEqual(execute_cleanup.call_count, 3)

    def test_preflight_reports_active_repository_task(self):
        repository = self._s3_repository("blocked-s3")
        task = create_task(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Active backup",
            request_payload={"repository_id": repository.id},
            resources=[
                {
                    "resource_type": TaskResource.Type.REPOSITORY,
                    "resource_id": repository.id,
                    "is_primary": True,
                }
            ],
        )

        preflight = repository_cleanup_preflight(repository=repository)

        self.assertFalse(preflight["allowed"])
        blocker = next(item for item in preflight["blockers"] if item["code"] == "active_task")
        self.assertEqual(blocker["task_uuid"], str(task.task_uuid))


class RepositoryCleanupApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            key="repository-cleanup-api-org",
            name="Repository Cleanup API Org",
        )
        self.user = get_user_model().objects.create_user(
            username="repository-cleanup-api@test.local",
            password="test-pass",
        )
        Membership.objects.create(
            organization=self.org,
            user=self.user,
            role=Membership.Role.ADMIN,
        )
        self.client.force_authenticate(self.user)
        self.repository = Repository.objects.create(
            organization_id=self.org.id,
            name="cleanup-api-s3",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_platform=Repository.S3Platform.AWS,
            s3_bucket="cleanup-api-bucket",
            config={"prefix": "cleanup/api/"},
        )

    def test_force_cleanup_is_selected_on_delete_and_requires_exact_confirmation(self):
        wrong = self.client.delete(
            f"/api/v1/storage/repositories/{self.repository.id}/",
            {
                "force": True,
                "confirmation": "force cleanup",
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        accepted = self.client.delete(
            f"/api/v1/storage/repositories/{self.repository.id}/",
            {
                "force": True,
                "confirmation": "FORCE CLEANUP",
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(wrong.status_code, 400, wrong.content)
        self.assertEqual(accepted.status_code, 202, accepted.content)
        self.assertEqual(accepted.data["operation_type"], "cleanup.repository")
        self.assertTrue(accepted.data["repository_cleanup"]["force"])

    def test_retry_and_force_action_endpoints_are_removed(self):
        for action in ("retry", "force"):
            response = self.client.post(
                f"/api/v1/storage/repositories/{self.repository.id}/cleanup/{action}/",
                {},
                format="json",
                HTTP_X_ORG_KEY=self.org.key,
            )
            self.assertEqual(response.status_code, 404, response.content)

    def test_force_preflight_allows_active_direct_nas_targets_with_warning(self):
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="force-direct-nas",
            repo_type=Repository.Type.NAS,
            nas_protocol=Repository.NasProtocol.NFS,
            status=Repository.Status.CREATED,
            health=Repository.Health.UNVERIFIED,
            config={"server_address": "10.0.0.10", "share_path": "/force"},
        )
        RepositoryUsageShard.objects.create(
            organization_id=self.org.id,
            repository_id=repository.id,
            node_id=99,
            repository_subdir="hp-repos/agent-99",
            status=RepositoryUsageShard.Status.SUCCESS,
        )

        response = self.client.post(
            f"/api/v1/storage/repositories/{repository.id}/cleanup/preflight/",
            {"force": True},
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.data["allowed"])
        self.assertTrue(response.data["force"])
        self.assertEqual(response.data["warnings"][0]["code"], "active_physical_targets")

    def test_cleanup_request_endpoint_is_removed(self):
        response = self.client.get(
            f"/api/v1/storage/repositories/{self.repository.id}/cleanup-requests/unused/",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_delete_unassociated_direct_nas_creates_logical_cleanup_task(self):
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="unused-direct-nas",
            repo_type=Repository.Type.NAS,
            nas_protocol=Repository.NasProtocol.NFS,
            status=Repository.Status.CREATED,
            health=Repository.Health.UNVERIFIED,
            config={"server_address": "10.0.0.9", "share_path": "/unused"},
        )

        response = self.client.delete(
            f"/api/v1/storage/repositories/{repository.id}/",
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 202, response.content)
        repository_task = RepositoryTask.objects.get(
            repository=repository,
            operation_type=RepositoryTask.OperationType.CLEANUP_REPOSITORY,
        )
        repository.refresh_from_db()
        self.assertEqual(repository.status, Repository.Status.REMOVING)
        self.assertIsNone(repository_task.execution_target_id)
        self.assertEqual(response.data["task_uuid"], str(repository_task.task.task_uuid))
