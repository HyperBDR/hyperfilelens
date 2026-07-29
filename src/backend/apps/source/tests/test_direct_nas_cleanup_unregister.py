from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.node.models import Node, NodeTask
from apps.protection.models import BackupConfig
from apps.source.services.internal.backup_source_delete import (
    BackupSourceDeleteFailed,
    delete_backup_sources,
    run_source_unregister_task,
)
from apps.storage.repositories.models import (
    Repository,
    RepositoryTask,
    RepositoryUsageShard,
)
from apps.storage.services.internal.repository_agent_operation import (
    RepositoryAgentOperationResult,
)
from apps.task.models import Task


class DirectNasCleanupUnregisterTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            key="direct-nas-unregister-org",
            name="Direct NAS Unregister Org",
        )
        self.agent = Node.objects.create(
            organization=self.org,
            name="direct-nas-agent",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            metadata={"inventory": {"capabilities": ["repository_cleanup_v1"]}},
        )
        self.repository = Repository.objects.create(
            organization_id=self.org.id,
            name="direct-nas",
            repo_type=Repository.Type.NAS,
            nas_protocol=Repository.NasProtocol.NFS,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            config={"server_address": "10.0.0.8", "share_path": "/backups"},
        )
        self.config = BackupConfig.objects.create(
            organization_id=self.org.id,
            name="direct NAS config",
            source_type="agent",
            source_ref_id=self.agent.id,
            repository_id=self.repository.id,
        )
        self.shard = RepositoryUsageShard.objects.create(
            organization_id=self.org.id,
            repository_id=self.repository.id,
            node_id=self.agent.id,
            repository_subdir=f"hp-repos/agent-{self.agent.id}",
            source_config_count=1,
            source_config_ids=[self.config.id],
            status=RepositoryUsageShard.Status.SUCCESS,
        )

    @mock.patch(
        "apps.source.services.internal.backup_source_delete.agent_connection_status",
        return_value="online",
    )
    @mock.patch(
        "apps.node.services.internal.node_lifecycle.start_node_remove",
        return_value={"task_id": 123, "operation_id": "remove-1", "state": "removing"},
    )
    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        return_value={"physical_cleanup": "deleted"},
    )
    def test_unregister_runs_independent_target_cleanup_before_removing_config(
        self,
        execute_cleanup,
        start_node_remove,
        agent_status,
    ):
        result = delete_backup_sources(
            org=self.org,
            ids=[f"agent:{self.agent.id}"],
        )

        cleanup_task = RepositoryTask.objects.get(
            repository=self.repository,
            operation_type=RepositoryTask.OperationType.CLEANUP_TARGET,
        )
        source_unregister = cleanup_task.triggered_by_task
        self.repository.refresh_from_db()
        self.shard.refresh_from_db()
        cleanup_task.task.refresh_from_db()
        source_unregister.refresh_from_db()
        self.assertEqual(cleanup_task.task.status, Task.Status.SUCCESS)
        self.assertEqual(source_unregister.status, Task.Status.RUNNING)
        self.assertEqual(result["result"], "waiting")
        cleanup_plan = source_unregister.request_payload["cleanup_plan"]
        self.assertEqual(cleanup_plan["source_id"], f"agent:{self.agent.id}")
        self.assertEqual(cleanup_plan["backup_config_ids"], [self.config.id])
        self.assertEqual(cleanup_plan["repository_ids"], [self.repository.id])
        self.assertEqual(self.repository.status, Repository.Status.CREATED)
        self.assertFalse(self.shard.is_active)
        self.assertFalse(BackupConfig.objects.filter(pk=self.config.id).exists())
        self.assertFalse(self.agent.is_deleted)
        self.assertEqual(
            result["repository_cleanup_tasks"][0]["triggered_by_task_uuid"],
            str(source_unregister.task_uuid),
        )
        execute_cleanup.assert_called_once()
        start_node_remove.assert_called_once()
        agent_status.assert_called()

        NodeTask.objects.create(
            organization=self.org,
            node=self.agent,
            kind="agent.uninstall",
            status=NodeTask.Status.SUCCESS,
            payload={"source_unregister_task_id": source_unregister.id},
            result={
                "mode": "local_detached",
                "completion_received_at": timezone.now().isoformat(),
                "cleanup_complete": True,
            },
            watchdog_deadline_at=timezone.now(),
            correlation_type="node.lifecycle",
            correlation_id=f"remove:{self.agent.id}",
        )

        completed = run_source_unregister_task(
            organization_id=self.org.id,
            task_uuid=str(source_unregister.task_uuid),
        )

        source_unregister.refresh_from_db()
        self.agent.refresh_from_db()
        self.assertEqual(completed["result"], "success")
        self.assertEqual(source_unregister.status, Task.Status.SUCCESS)
        self.assertTrue(self.agent.is_deleted)

    @mock.patch(
        "apps.source.services.internal.backup_source_delete.agent_connection_status",
        return_value="online",
    )
    @mock.patch(
        "apps.node.services.internal.node_lifecycle.start_node_remove",
        return_value={"task_id": 123, "operation_id": "remove-1", "state": "removing"},
    )
    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        side_effect=[
            RepositoryAgentOperationResult(
                waiting=True,
                node_task_id=uuid4(),
                result={},
            ),
            {"physical_cleanup": "deleted"},
        ],
    )
    def test_unregister_waits_for_target_cleanup_then_agent_uninstall(
        self,
        execute_cleanup,
        start_node_remove,
        agent_status,
    ):
        waiting = delete_backup_sources(
            org=self.org,
            ids=[f"agent:{self.agent.id}"],
        )

        unregister_task = Task.objects.get(pk=waiting["task_id"])
        cleanup_task = RepositoryTask.objects.get(triggered_by_task=unregister_task)
        unregister_task.refresh_from_db()
        cleanup_task.task.refresh_from_db()
        self.assertEqual(waiting["result"], "waiting")
        self.assertEqual(unregister_task.status, Task.Status.RUNNING)
        self.assertEqual(cleanup_task.task.status, Task.Status.RUNNING)
        self.assertTrue(BackupConfig.objects.filter(pk=self.config.id).exists())
        self.assertFalse(self.agent.is_deleted)

        with (
            mock.patch(
                "apps.source.tasks.source_unregister.queue_source_unregister_task"
            ) as queue_parent,
            self.captureOnCommitCallbacks(execute=True),
        ):
            resumed = run_source_unregister_task(
                organization_id=self.org.id,
                task_uuid=str(unregister_task.task_uuid),
            )

        unregister_task.refresh_from_db()
        cleanup_task.task.refresh_from_db()
        self.assertEqual(resumed["result"], "waiting")
        self.assertEqual(unregister_task.status, Task.Status.RUNNING)
        self.assertEqual(cleanup_task.task.status, Task.Status.SUCCESS)
        self.assertFalse(BackupConfig.objects.filter(pk=self.config.id).exists())
        queue_parent.assert_called_once_with(
            task_id=unregister_task.id,
            countdown_seconds=1,
        )
        execute_cleanup.assert_has_calls(
            [
                mock.call(cleanup_task, allow_dispatch=True),
                mock.call(cleanup_task, allow_dispatch=False),
            ]
        )
        start_node_remove.assert_called_once()
        agent_status.assert_called()

    @mock.patch(
        "apps.source.services.internal.backup_source_delete.agent_connection_status",
        return_value="online",
    )
    @mock.patch(
        "apps.node.services.internal.node_lifecycle.start_node_remove",
    )
    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        return_value={"physical_cleanup": "deleted"},
    )
    def test_force_unregister_finishes_if_agent_goes_offline_before_uninstall_dispatch(
        self,
        _execute_cleanup,
        start_node_remove,
        _agent_status,
    ):
        def purge_offline_node(**_kwargs):
            self.agent.soft_delete()
            return {
                "state": "removed",
                "purged": True,
                "force": True,
                "cleanup_complete": False,
                "cleanup_failures": [
                    {
                        "code": "agent_offline",
                        "detail": "Agent disconnected before uninstall dispatch.",
                    }
                ],
                "retained_resources": ["agent_installation"],
            }

        start_node_remove.side_effect = purge_offline_node

        result = delete_backup_sources(
            org=self.org,
            ids=[f"agent:{self.agent.id}"],
            force=True,
        )

        unregister_task = Task.objects.get(pk=result["task_id"])
        self.assertEqual(result["result"], "partial_success")
        self.assertEqual(result["pending_removals"], [])
        self.assertEqual(result["deleted"], [f"agent:{self.agent.id}"])
        self.assertFalse(result["cleanup_complete"])
        self.assertEqual(result["retained_resources"], ["agent_installation"])
        self.assertEqual(unregister_task.status, Task.Status.SUCCESS)
        start_node_remove.assert_called_once()

    @mock.patch(
        "apps.source.services.internal.backup_source_delete.agent_connection_status",
        return_value="online",
    )
    @mock.patch(
        "apps.node.services.internal.node_lifecycle.start_node_remove",
    )
    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        return_value={"physical_cleanup": "deleted"},
    )
    def test_parent_redelivery_waits_for_its_existing_agent_uninstall(
        self,
        _execute_cleanup,
        start_node_remove,
        _agent_status,
    ):
        def create_uninstall(**kwargs):
            parent_id = kwargs["triggered_by_task_id"]
            node_task = NodeTask.objects.create(
                organization=self.org,
                node=self.agent,
                kind="agent.uninstall",
                status=NodeTask.Status.RUNNING,
                payload={"source_unregister_task_id": parent_id},
                result={"mode": "local_detached"},
                watchdog_deadline_at=timezone.now() + timezone.timedelta(minutes=10),
                correlation_type="node.lifecycle",
                correlation_id=f"remove:{self.agent.id}",
            )
            return {
                "task_id": str(node_task.id),
                "operation_id": node_task.correlation_id,
                "state": "removing",
            }

        start_node_remove.side_effect = create_uninstall
        first = delete_backup_sources(
            org=self.org,
            ids=[f"agent:{self.agent.id}"],
        )
        unregister_task = Task.objects.get(pk=first["task_id"])

        redelivered = run_source_unregister_task(
            organization_id=self.org.id,
            task_uuid=str(unregister_task.task_uuid),
        )

        unregister_task.refresh_from_db()
        self.assertEqual(redelivered["result"], "waiting")
        self.assertEqual(unregister_task.status, Task.Status.RUNNING)
        self.assertEqual(len(redelivered["pending_removals"]), 1)
        start_node_remove.assert_called_once()

    @mock.patch(
        "apps.source.services.internal.backup_source_delete.agent_connection_status",
        return_value="online",
    )
    @mock.patch(
        "apps.storage.services.internal.repository_cleanup._execute_physical_cleanup",
        side_effect=RuntimeError("agent unreachable"),
    )
    def test_cleanup_failure_fails_triggering_unregister_and_preserves_source_configuration(
        self,
        execute_cleanup,
        agent_status,
    ):
        with self.assertRaises(BackupSourceDeleteFailed):
            delete_backup_sources(
                org=self.org,
                ids=[f"agent:{self.agent.id}"],
            )

        cleanup_task = RepositoryTask.objects.get(
            repository=self.repository,
            operation_type=RepositoryTask.OperationType.CLEANUP_TARGET,
        )
        cleanup_task.task.refresh_from_db()
        cleanup_task.triggered_by_task.refresh_from_db()
        self.agent.refresh_from_db()
        self.assertEqual(cleanup_task.task.status, Task.Status.FAILED)
        self.assertEqual(cleanup_task.triggered_by_task.status, Task.Status.FAILED)
        self.assertTrue(BackupConfig.objects.filter(pk=self.config.id).exists())
        self.assertFalse(self.agent.is_deleted)
        execute_cleanup.assert_called_once()
        agent_status.assert_called()

        user = get_user_model().objects.create_user(
            username="direct-nas-retry@test.local",
            password="test-pass",
        )
        Membership.objects.create(
            organization=self.org,
            user=user,
            role=Membership.Role.ADMIN,
        )
        client = APIClient()
        client.force_authenticate(user)
        with mock.patch("apps.task.api.views.task.current_app.send_task") as queue_unregister:
            retry_response = client.post(
                f"/api/v1/tasks/{cleanup_task.triggered_by_task.task_uuid}/retry/",
                {},
                format="json",
                HTTP_X_ORG_KEY=self.org.key,
            )
        self.assertEqual(retry_response.status_code, 200, retry_response.content)
        queue_unregister.assert_called_once_with(
            "apps.source.tasks.source_unregister.execute_source_unregister_task",
            kwargs={"task_id": cleanup_task.triggered_by_task_id},
        )
