from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.node.models import Node
from apps.storage.repositories.models import (
    Repository,
    RepositoryExecutionTarget,
    RepositoryTask,
    RepositoryUsageShard,
)
from apps.storage.services.internal.repository_operations import (
    create_repository_operation_task,
    discover_repository_execution_targets,
    finalize_repository_operation,
    schedule_due_maintenance,
)
from apps.task.models import Task
from apps.task.services.interface import start_task


class RepositoryTaskTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="repository-task-org", name="Repository Task Org")
        self.repository = Repository.objects.create(
            organization_id=self.org.id,
            name="maintenance-s3",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_platform=Repository.S3Platform.AWS,
            s3_bucket="maintenance-bucket",
        )

    def test_discovers_controller_target_with_stable_owner(self):
        count = discover_repository_execution_targets(
            now=timezone.make_aware(datetime(2026, 7, 14, 1, 0, 0)),
        )

        self.assertEqual(count, 1)
        target = RepositoryExecutionTarget.objects.get(repository=self.repository)
        self.assertEqual(target.target_key, f"repository:{self.repository.id}")
        self.assertEqual(target.owner_type, RepositoryExecutionTarget.OwnerType.CONTROLLER)
        self.assertEqual(target.owner_identity, "hfl-maintenance@controller")
        self.assertIsNotNone(target.maintenance_state.next_quick_due_at)

    def test_target_lock_prevents_duplicate_repository_tasks(self):
        discover_repository_execution_targets()
        target = RepositoryExecutionTarget.objects.get(repository=self.repository)

        first = create_repository_operation_task(
            target_id=target.id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_QUICK,
        )
        duplicate = create_repository_operation_task(
            target_id=target.id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_FULL,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(duplicate)
        self.assertEqual(first.task.task_type, Task.Type.REPOSITORY_OPERATION)
        self.assertEqual(first.task.display_name, "Quick maintenance · maintenance-s3")
        self.assertEqual(first.task.resources.get().resource_id, self.repository.id)
        self.assertTrue(first.task.resources.get().is_primary)

    def test_proxy_nas_maintenance_keeps_repository_name(self):
        proxy = Node.objects.create(
            organization=self.org,
            name="storage-proxy",
            role=Node.Role.PROXY,
            status=Node.Status.ONLINE,
        )
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="proxy-nas",
            repo_type=Repository.Type.NAS,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            nas_protocol=Repository.NasProtocol.NFS,
            bind_node_type=Repository.BindNodeType.PROXY,
            bind_node_id=proxy.id,
        )
        discover_repository_execution_targets()

        task = create_repository_operation_task(
            target_id=repository.execution_targets.get().id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_FULL,
        )

        self.assertEqual(task.task.display_name, "Full maintenance · proxy-nas")

    def test_direct_nas_maintenance_uses_backup_source_names(self):
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="direct-nas",
            repo_type=Repository.Type.NAS,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            nas_protocol=Repository.NasProtocol.NFS,
        )
        nodes = [
            Node.objects.create(
                organization=self.org,
                name=name,
                role=Node.Role.AGENT,
                status=Node.Status.ONLINE,
            )
            for name in ("Finance-Server", "HR-Server")
        ]
        for node in nodes:
            RepositoryUsageShard.objects.create(
                organization_id=self.org.id,
                repository_id=repository.id,
                node_id=node.id,
                repository_subdir=f"hp-repos/agent-{node.id}",
                status=RepositoryUsageShard.Status.SUCCESS,
            )
        discover_repository_execution_targets()
        targets = {
            target.owner_node_id: target
            for target in RepositoryExecutionTarget.objects.filter(repository=repository)
        }

        quick = create_repository_operation_task(
            target_id=targets[nodes[0].id].id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_QUICK,
        )
        full = create_repository_operation_task(
            target_id=targets[nodes[1].id].id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_FULL,
        )

        self.assertEqual(quick.task.display_name, "Quick maintenance · Finance-Server")
        self.assertEqual(full.task.display_name, "Full maintenance · HR-Server")

    def test_direct_nas_duplicate_source_names_include_node_ids(self):
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="duplicate-source-nas",
            repo_type=Repository.Type.NAS,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            nas_protocol=Repository.NasProtocol.NFS,
        )
        nodes = [
            Node.objects.create(
                organization=self.org,
                name="Finance-Server",
                role=Node.Role.AGENT,
                status=Node.Status.ONLINE,
            )
            for _ in range(2)
        ]
        for node in nodes:
            RepositoryUsageShard.objects.create(
                organization_id=self.org.id,
                repository_id=repository.id,
                node_id=node.id,
                repository_subdir=f"hp-repos/agent-{node.id}",
                status=RepositoryUsageShard.Status.SUCCESS,
            )
        discover_repository_execution_targets()

        for node in nodes:
            target = RepositoryExecutionTarget.objects.get(
                repository=repository,
                owner_node_id=node.id,
            )
            task = create_repository_operation_task(
                target_id=target.id,
                operation_type=RepositoryTask.OperationType.MAINTENANCE_QUICK,
            )
            self.assertEqual(
                task.task.display_name,
                f"Quick maintenance · Finance-Server (#{node.id})",
            )

    def test_direct_nas_source_name_survives_soft_delete_and_has_missing_fallback(self):
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="source-fallback-nas",
            repo_type=Repository.Type.NAS,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            nas_protocol=Repository.NasProtocol.NFS,
        )
        node = Node.objects.create(
            organization=self.org,
            name="Archived-Server",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
        )
        for node_id in (node.id, 999999):
            RepositoryUsageShard.objects.create(
                organization_id=self.org.id,
                repository_id=repository.id,
                node_id=node_id,
                repository_subdir=f"hp-repos/agent-{node_id}",
                status=RepositoryUsageShard.Status.SUCCESS,
            )
        discover_repository_execution_targets()
        node.soft_delete()

        archived_target = RepositoryExecutionTarget.objects.get(
            repository=repository,
            owner_node_id=node.id,
        )
        missing_target = RepositoryExecutionTarget.objects.get(
            repository=repository,
            owner_node_id=999999,
        )
        archived = create_repository_operation_task(
            target_id=archived_target.id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_QUICK,
        )
        missing = create_repository_operation_task(
            target_id=missing_target.id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_FULL,
        )

        self.assertEqual(archived.task.display_name, "Quick maintenance · Archived-Server")
        self.assertEqual(missing.task.display_name, "Full maintenance · Backup Source #999999")

    def test_finalize_repository_operation_locks_nullable_target_separately(self):
        discover_repository_execution_targets()
        target = RepositoryExecutionTarget.objects.get(repository=self.repository)
        repository_task = create_repository_operation_task(
            target_id=target.id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_QUICK,
        )
        start_task(
            task_uuid=repository_task.task.task_uuid,
            organization_id=self.org.id,
        )

        task = finalize_repository_operation(
            repository_task_id=repository_task.id,
            succeeded=True,
            result_payload={"operation_type": RepositoryTask.OperationType.MAINTENANCE_QUICK},
        )

        target.refresh_from_db()
        target.maintenance_state.refresh_from_db()
        self.assertEqual(task.status, Task.Status.SUCCESS)
        self.assertEqual(task.progress, 100)
        self.assertIsNotNone(task.finished_at)
        self.assertIsNone(target.active_task_id)
        self.assertIsNotNone(target.maintenance_state.last_quick_success_at)
        self.assertEqual(target.maintenance_state.consecutive_failures, 0)

    @patch.dict(
        "os.environ",
        {
            "STORAGE_MAINTENANCE_TIMEZONE": "UTC",
            "STORAGE_MAINTENANCE_FULL_WINDOW_START": "00:00",
            "STORAGE_MAINTENANCE_FULL_WINDOW_END": "06:00",
        },
    )
    def test_scheduler_runs_quick_outside_full_window(self):
        now = timezone.make_aware(datetime(2026, 7, 14, 12, 0, 0))

        scheduled = schedule_due_maintenance(now=now)

        self.assertEqual(len(scheduled), 1)
        repository_task = RepositoryTask.objects.get(pk=scheduled[0])
        self.assertEqual(repository_task.operation_type, RepositoryTask.OperationType.MAINTENANCE_QUICK)
        self.assertEqual(repository_task.task.trigger_type, Task.TriggerType.SYSTEM)

    @patch.dict(
        "os.environ",
        {
            "STORAGE_MAINTENANCE_TIMEZONE": "UTC",
            "STORAGE_MAINTENANCE_FULL_WINDOW_START": "00:00",
            "STORAGE_MAINTENANCE_FULL_WINDOW_END": "06:00",
        },
    )
    def test_scheduler_runs_full_inside_full_window(self):
        now = timezone.make_aware(datetime(2026, 7, 14, 5, 59, 59))

        scheduled = schedule_due_maintenance(now=now)

        self.assertEqual(len(scheduled), 1)
        repository_task = RepositoryTask.objects.get(pk=scheduled[0])
        self.assertEqual(repository_task.operation_type, RepositoryTask.OperationType.MAINTENANCE_FULL)


class RepositoryTasksApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(
            username="repository-tasks@test.local",
            email="repository-tasks@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="repository-tasks-api", name="Repository Tasks API")
        Membership.objects.create(user=user, organization=self.org, role=Membership.Role.ADMIN)
        self.client.force_authenticate(user=user)
        self.repository = Repository.objects.create(
            organization_id=self.org.id,
            name="task-list-s3",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_platform=Repository.S3Platform.AWS,
            s3_bucket="task-list-bucket",
        )
        discover_repository_execution_targets()
        self.repository_task = create_repository_operation_task(
            target_id=self.repository.execution_targets.get().id,
            operation_type=RepositoryTask.OperationType.MAINTENANCE_FULL,
        )

    def test_lists_only_repository_operations_with_metadata(self):
        response = self.client.get(
            f"/api/v1/storage/repositories/{self.repository.id}/tasks/",
            {"operation_type": "maintenance.full"},
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 200, response.content)
        rows = response.data["data"]["list"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task_uuid"], str(self.repository_task.task.task_uuid))
        self.assertEqual(rows[0]["operation_type"], "maintenance.full")
        self.assertEqual(rows[0]["repository_owner"]["identity"], "hfl-maintenance@controller")

    def test_task_search_field_filters_name_and_uuid(self):
        base_url = f"/api/v1/storage/repositories/{self.repository.id}/tasks/"
        name_response = self.client.get(
            base_url,
            {"search": self.repository_task.task.display_name, "search_field": "name"},
            HTTP_X_ORG_KEY=self.org.key,
        )
        uuid_response = self.client.get(
            base_url,
            {"search": str(self.repository_task.task.task_uuid), "search_field": "uuid"},
            HTTP_X_ORG_KEY=self.org.key,
        )
        uuid_as_name_response = self.client.get(
            base_url,
            {"search": str(self.repository_task.task.task_uuid), "search_field": "name"},
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(name_response.status_code, 200, name_response.content)
        self.assertEqual(uuid_response.status_code, 200, uuid_response.content)
        self.assertEqual(uuid_as_name_response.status_code, 200, uuid_as_name_response.content)
        self.assertEqual(len(name_response.data["data"]["list"]), 1)
        self.assertEqual(len(uuid_response.data["data"]["list"]), 1)
        self.assertEqual(len(uuid_as_name_response.data["data"]["list"]), 0)

    def test_task_search_field_rejects_unknown_value(self):
        response = self.client.get(
            f"/api/v1/storage/repositories/{self.repository.id}/tasks/",
            {"search": "maintenance", "search_field": "invalid"},
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 400, response.content)

    def test_repository_tasks_are_organization_scoped(self):
        other = Organization.objects.create(key="other-task-org", name="Other")
        response = self.client.get(
            f"/api/v1/storage/repositories/{self.repository.id}/tasks/",
            HTTP_X_ORG_KEY=other.key,
        )
        self.assertIn(response.status_code, {403, 404})

    def test_repository_operations_cannot_be_created_or_cancelled_publicly(self):
        create = self.client.post(
            "/api/v1/tasks/",
            {
                "task_type": "repository_operation",
                "display_name": "Manual maintenance",
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(create.status_code, 400)

        cancel = self.client.post(
            f"/api/v1/tasks/{self.repository_task.task.task_uuid}/cancel/",
            {},
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(cancel.status_code, 400)
