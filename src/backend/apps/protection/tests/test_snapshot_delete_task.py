from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.iam.models import Membership, Organization
from apps.node.models import Node
from apps.protection.models import (
    BackupConfig,
    BackupConfigDirectory,
    BackupSourceSnapshot,
    BackupSourceSnapshotDirectory,
)
from apps.protection.services.backup_source_snapshot import create_source_snapshot
from apps.protection.services.snapshot_delete import (
    create_and_queue_snapshot_delete_task,
    create_snapshot_delete_task,
    run_snapshot_delete_task,
    snapshot_delete_retry_delay,
)
from apps.storage.repositories.models import Repository
from apps.task.models import Task, TaskResource


class SnapshotDeleteTaskTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="snapshot-delete@test.local",
            email="snapshot-delete@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="snapshot-delete-org", name="Snapshot Delete Org")
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.Role.ADMIN)
        self.agent = Node.objects.create(
            organization=self.org,
            name="snapshot-delete-agent",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
        )
        self.repository = Repository.objects.create(
            organization_id=self.org.id,
            name="snapshot-delete-repo",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_platform=Repository.S3Platform.CUSTOM,
            s3_bucket="snapshot-delete-bucket",
            config={
                "endpoint": "s3.example.internal:9000",
                "region": "cn-test-1",
                "prefix": "kopia/delete",
                "access_key_id": "ak",
                "secret_access_key": "sk",
                "kopia_password": "123456",
                "use_tls": False,
            },
        )
        self.config = BackupConfig.objects.create(
            organization_id=self.org.id,
            name="Snapshot delete config",
            source_type="agent",
            source_ref_id=self.agent.id,
            repository_id=self.repository.id,
        )
        self.dir_a = BackupConfigDirectory.objects.create(
            organization_id=self.org.id,
            backup_config=self.config,
            path="/data/a",
            display_name="a",
        )
        self.dir_b = BackupConfigDirectory.objects.create(
            organization_id=self.org.id,
            backup_config=self.config,
            path="/data/b",
            display_name="b",
        )
        self.task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Snapshot delete source task",
        )
        self.snapshot = create_source_snapshot(
            organization_id=self.org.id,
            source_type="agent",
            source_ref_id=self.agent.id,
            backup_config_id=self.config.id,
            repository_id=self.repository.id,
            task_id=self.task.id,
            task_uuid=self.task.task_uuid,
            idempotency_key="snapshot-delete-source",
            status=BackupSourceSnapshot.Status.AVAILABLE,
            directory_count=2,
        )
        BackupSourceSnapshotDirectory.objects.create(
            source_snapshot=self.snapshot,
            organization_id=self.org.id,
            backup_config_id=self.config.id,
            backup_config_dir_id=self.dir_a.id,
            source_path="/data/a",
            repository_id=self.repository.id,
            kopia_snapshot_id="kopia-a",
            status=BackupSourceSnapshotDirectory.Status.AVAILABLE,
        )
        BackupSourceSnapshotDirectory.objects.create(
            source_snapshot=self.snapshot,
            organization_id=self.org.id,
            backup_config_id=self.config.id,
            backup_config_dir_id=self.dir_b.id,
            source_path="/data/b",
            repository_id=self.repository.id,
            kopia_snapshot_id="kopia-b",
            status=BackupSourceSnapshotDirectory.Status.AVAILABLE,
        )

    @patch("apps.protection.services.snapshot_delete.run_agent_task_sync")
    def test_run_snapshot_delete_task_marks_logical_snapshot_deleted(self, mock_run_agent_task_sync):
        task = create_snapshot_delete_task(source_snapshot=self.snapshot)
        source_resource = task.resources.get(resource_type=TaskResource.Type.BACKUP_SOURCE)
        self.assertEqual(source_resource.resource_subtype, "agent")
        self.assertEqual(source_resource.resource_id, self.agent.id)
        mock_run_agent_task_sync.return_value = SimpleNamespace(
            task=SimpleNamespace(id="node-delete-1", status="success", last_error=""),
            result={
                "deleted_count": 2,
                "failed_count": 0,
                "results": [
                    {"kopia_snapshot_id": "kopia-a", "status": "success"},
                    {"kopia_snapshot_id": "kopia-b", "status": "success"},
                ],
            },
            ok=True,
            timed_out=False,
        )

        result = run_snapshot_delete_task(
            organization_id=self.org.id,
            task_uuid=str(task.task_uuid),
            source_snapshot_id=self.snapshot.id,
        )

        self.snapshot.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.SUCCESS)
        self.assertEqual(self.snapshot.status, BackupSourceSnapshot.Status.DELETED)
        self.assertIsNotNone(self.snapshot.deleted_at)
        self.assertEqual(result["deleted_count"], 2)
        self.assertFalse(
            BackupSourceSnapshotDirectory.objects.filter(
                source_snapshot=self.snapshot,
            ).exclude(status=BackupSourceSnapshotDirectory.Status.DELETED).exists()
        )
        payload = mock_run_agent_task_sync.call_args.kwargs["payload"]
        self.assertEqual(payload["kopia_snapshot_ids"], ["kopia-a", "kopia-b"])
        events = task.events.filter(message="Deleting physical Kopia snapshot").order_by("seq")
        self.assertEqual(events.count(), 2)
        self.assertEqual(events[0].metadata["kopia_snapshot_display"], "kopia-a (/data/a)")
        self.assertEqual(events[1].metadata["kopia_snapshot_display"], "kopia-b (/data/b)")

    @patch("apps.protection.services.snapshot_delete.run_agent_task_sync")
    def test_run_snapshot_delete_task_keeps_logical_snapshot_when_partial_delete_fails(self, mock_run_agent_task_sync):
        task = create_snapshot_delete_task(source_snapshot=self.snapshot)
        mock_run_agent_task_sync.return_value = SimpleNamespace(
            task=SimpleNamespace(id="node-delete-2", status="failed", last_error="delete failed"),
            result={
                "deleted_count": 1,
                "failed_count": 1,
                "results": [
                    {"kopia_snapshot_id": "kopia-a", "status": "success"},
                    {"kopia_snapshot_id": "kopia-b", "status": "failed", "error_message": "boom"},
                ],
            },
            ok=False,
            timed_out=False,
        )

        run_snapshot_delete_task(
            organization_id=self.org.id,
            task_uuid=str(task.task_uuid),
            source_snapshot_id=self.snapshot.id,
        )

        self.snapshot.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.FAILED)
        self.assertEqual(self.snapshot.status, BackupSourceSnapshot.Status.DELETE_FAILED)
        self.assertEqual(
            BackupSourceSnapshotDirectory.objects.get(kopia_snapshot_id="kopia-a").status,
            BackupSourceSnapshotDirectory.Status.DELETED,
        )
        self.assertEqual(
            BackupSourceSnapshotDirectory.objects.get(kopia_snapshot_id="kopia-b").status,
            BackupSourceSnapshotDirectory.Status.AVAILABLE,
        )

    @patch("apps.protection.services.snapshot_delete.run_agent_task_sync")
    def test_already_absent_physical_snapshots_complete_logical_delete(self, mock_run_agent_task_sync):
        task = create_snapshot_delete_task(source_snapshot=self.snapshot)
        mock_run_agent_task_sync.return_value = SimpleNamespace(
            task=SimpleNamespace(id="node-delete-absent", status="failed", last_error="2 deletes failed"),
            result={
                "deleted_count": 0,
                "failed_count": 2,
                "results": [
                    {
                        "kopia_snapshot_id": "kopia-a",
                        "status": "failed",
                        "delete": {"stderr": "no snapshots matched kopia-a"},
                    },
                    {
                        "kopia_snapshot_id": "kopia-b",
                        "status": "failed",
                        "delete": {"stderr": "no snapshots matched kopia-b"},
                    },
                ],
            },
            ok=False,
            timed_out=False,
        )

        result = run_snapshot_delete_task(
            organization_id=self.org.id,
            task_uuid=str(task.task_uuid),
            source_snapshot_id=self.snapshot.id,
        )

        self.snapshot.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(self.snapshot.status, BackupSourceSnapshot.Status.DELETED)
        self.assertEqual(task.status, Task.Status.SUCCESS)
        self.assertEqual(result["already_absent_count"], 2)

    def test_retry_delay_sequence_caps_at_two_hours(self):
        self.assertEqual(
            [int(snapshot_delete_retry_delay(i).total_seconds() / 60) for i in range(9)],
            [1, 4, 16, 30, 60, 120, 120, 120, 120],
        )

    @patch("apps.protection.services.snapshot_delete.run_agent_task_sync")
    def test_delete_failed_manual_retry_reuses_original_task(self, mock_run_agent_task_sync):
        task = create_snapshot_delete_task(source_snapshot=self.snapshot)
        mock_run_agent_task_sync.return_value = SimpleNamespace(
            task=SimpleNamespace(id="node-delete-retry", status="failed", last_error="temporary failure"),
            result={
                "results": [
                    {"kopia_snapshot_id": "kopia-a", "status": "success"},
                    {"kopia_snapshot_id": "kopia-b", "status": "failed", "error_message": "temporary"},
                ],
            },
            ok=False,
            timed_out=False,
        )
        run_snapshot_delete_task(
            organization_id=self.org.id,
            task_uuid=str(task.task_uuid),
            source_snapshot_id=self.snapshot.id,
        )

        retried = create_and_queue_snapshot_delete_task(source_snapshot=self.snapshot)

        self.snapshot.refresh_from_db()
        retried.refresh_from_db()
        self.assertEqual(retried.id, task.id)
        self.assertEqual(retried.task_uuid, task.task_uuid)
        self.assertEqual(retried.status, Task.Status.PENDING)
        self.assertEqual(retried.retry_count, 1)
        self.assertEqual(self.snapshot.status, BackupSourceSnapshot.Status.DELETING)
        self.assertEqual(
            retried.request_payload["kopia_snapshot_ids"],
            ["kopia-a", "kopia-b"],
        )
