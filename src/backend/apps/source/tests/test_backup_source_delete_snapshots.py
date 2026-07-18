from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.node import agent_paths
from apps.node.models import Node
from apps.protection.models import (
    BackupConfig,
    BackupConfigDirectory,
    BackupSourceSnapshotDirectory,
)
from apps.protection.services.backup_source_snapshot import create_source_snapshot
from apps.source.models import SourceResource
from apps.storage.repositories.models import Repository
from apps.task.models import Task


MOUNTS_ROOT = agent_paths.agent_mounts_dir()


def custom_mount(leaf: str) -> str:
    return f"{MOUNTS_ROOT}/custom/{leaf}"


class BackupSourceDeleteSnapshotTaskTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="nas-delete-snap@test.local",
            email="nas-delete-snap@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="nas-delete-snap-org", name="NAS Delete Snap Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.proxy = Node.objects.create(
            organization=self.org,
            name="proxy-delete-snap",
            role=Node.Role.PROXY,
            status=Node.Status.ONLINE,
        )
        self.resource = SourceResource.objects.create(
            organization_id=self.org.id,
            name="nas-delete-snap",
            resource_type="nas",
            config={
                "protocol": "nfs",
                "server": "192.168.7.61",
                "export_path": "/data/nfs_backup",
                "path": custom_mount("nfs-delete-snap"),
            },
            bound_node=self.proxy,
            mount_status="mounted",
            mount_point=custom_mount("nfs-delete-snap"),
        )
        self.repository = Repository.objects.create(
            organization_id=self.org.id,
            name="s3-delete-snap-repo",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_platform=Repository.S3Platform.CUSTOM,
            s3_bucket="delete-snap-bucket",
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
            name="NAS delete snap config",
            source_type="nas",
            source_ref_id=self.resource.id,
            repository_id=self.repository.id,
        )
        self.directory = BackupConfigDirectory.objects.create(
            organization_id=self.org.id,
            backup_config=self.config,
            path="/data",
            display_name="data",
        )
        self.backup_task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="NAS delete snap backup",
        )
        self.snapshot = create_source_snapshot(
            organization_id=self.org.id,
            source_type="nas",
            source_ref_id=self.resource.id,
            backup_config_id=self.config.id,
            repository_id=self.repository.id,
            task_id=self.backup_task.id,
            task_uuid=self.backup_task.task_uuid,
            idempotency_key="nas-delete-snap",
        )
        BackupSourceSnapshotDirectory.objects.create(
            source_snapshot=self.snapshot,
            organization_id=self.org.id,
            backup_config_id=self.config.id,
            backup_config_dir_id=self.directory.id,
            source_path="/data",
            repository_id=self.repository.id,
            kopia_snapshot_id="kopia-delete-fail",
            status=BackupSourceSnapshotDirectory.Status.AVAILABLE,
        )
        self.client.force_authenticate(user=self.user)

    def _headers(self):
        return {"HTTP_X_ORG_KEY": self.org.key}

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        SOURCE_UNREGISTER_EAGER=True,
    )
    @patch("apps.protection.services.snapshot_delete.run_agent_task_sync")
    def test_bulk_delete_keeps_failed_snapshot_remove_task(self, mock_run_agent_task_sync):
        mock_run_agent_task_sync.return_value = SimpleNamespace(
            task=SimpleNamespace(id="node-delete-fail", status="failed", last_error="kopia delete failed"),
            result={
                "deleted_count": 0,
                "failed_count": 1,
                "results": [
                    {
                        "kopia_snapshot_id": "kopia-delete-fail",
                        "status": "failed",
                        "error_message": "snapshot not found",
                    }
                ],
            },
            ok=False,
            timed_out=False,
        )

        nas_key = f"nas:{self.resource.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/bulk-delete/",
            {"ids": [nas_key], "force": False, "confirmation": "UNREGISTER"},
            format="json",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.resource.refresh_from_db()
        self.assertFalse(self.resource.is_deleted)
        failed_tasks = Task.objects.filter(
            organization_id=self.org.id,
            task_type=Task.Type.SNAPSHOT_DELETE,
            status=Task.Status.FAILED,
        )
        self.assertEqual(failed_tasks.count(), 1)
        self.assertIn("kopia delete failed", failed_tasks.first().error_message or "")

    def test_delete_preflight_ignores_existing_snapshots_when_repo_online(self):
        nas_key = f"nas:{self.resource.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/delete-preflight/",
            {"ids": [nas_key]},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["strict_may_fail"])
        self.assertEqual(response.data["risks"], [])

    def test_delete_preflight_flags_offline_repository(self):
        self.repository.health = Repository.Health.OFFLINE
        self.repository.save(update_fields=["health"])
        nas_key = f"nas:{self.resource.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/delete-preflight/",
            {"ids": [nas_key]},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["strict_may_fail"])
        self.assertTrue(any(row["code"] == "repository_unreachable" for row in response.data["risks"]))
