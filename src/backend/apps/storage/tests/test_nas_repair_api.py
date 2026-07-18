"""Tests for the NAS storage repository "repair" endpoint.

The repair flow has three top-level scenarios:

* The repository is not bound to a Proxy. The endpoint may either save
  config-only changes, or bind a new Proxy (which triggers Kopia init).
* The repository is already bound to a Proxy. The endpoint may save
  config-only changes, or replace the Proxy with a different online one.
  Replacing the Proxy must not re-initialize the Kopia repository; it must
  mount the share on the new Proxy and unmount the old one.
* The repository is currently being used by a running or pending backup
  task. The endpoint must refuse to swap the Proxy in this state.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.protection.models import BackupConfig
from apps.storage.repositories.models import Credential, Repository
from apps.storage.services.internal.repository_errors import (
    REPOSITORY_ALREADY_EXISTS_CODE,
    RepositoryAlreadyExistsError,
)
from apps.task.models import Task


class NasRepairApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="nas-repair@test.local",
            email="nas-repair@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(
            key="nas-repair-org",
            name="NAS Repair Org",
        )
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.client.force_authenticate(user=self.user)
        self.proxy_a = Node.objects.create(
            organization=self.org,
            name="proxy-a",
            role=NodeRole.PROXY,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.31",
        )
        self.proxy_b = Node.objects.create(
            organization=self.org,
            name="proxy-b",
            role=NodeRole.PROXY,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.32",
        )
        self.proxy_offline = Node.objects.create(
            organization=self.org,
            name="proxy-c",
            role=NodeRole.PROXY,
            status=Node.Status.OFFLINE,
            ip_address="10.0.0.33",
        )

    def _headers(self):
        return {"HTTP_X_ORG_KEY": self.org.key}

    def _make_unbound_nas(self, *, protocol=Repository.NasProtocol.SMB):
        return Repository.objects.create(
            organization_id=self.org.id,
            name="unbound-nas",
            repo_type=Repository.Type.NAS,
            nas_protocol=protocol,
            status=Repository.Status.CREATED,
            health=Repository.Health.UNVERIFIED,
            config={
                "server_address": "10.0.0.10",
                "share_path": "/backup",
                "mount_options": "ro,soft",
                "quota_gb": 100,
                "smb_username": "u",
                "smb_password": "p",
            },
        )

    def _make_bound_nas(self):
        return Repository.objects.create(
            organization_id=self.org.id,
            name="bound-nas",
            repo_type=Repository.Type.NAS,
            nas_protocol=Repository.NasProtocol.SMB,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            bind_node_type=Repository.BindNodeType.PROXY,
            bind_node_id=self.proxy_a.id,
            config={
                "server_address": "10.0.0.10",
                "share_path": "/backup",
                "mount_options": "ro,soft",
                "quota_gb": 100,
                "smb_username": "u",
                "smb_password": "p",
            },
        )

    # --- save-only scenarios ---------------------------------------------

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    def test_repair_unbound_save_only(self, _sync):
        repo = self._make_unbound_nas()
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {
                "name": "renamed",
                "config": {
                    "quota_gb": 200,
                    "mount_options": "rw,soft",
                },
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        repo.refresh_from_db()
        self.assertEqual(repo.name, "renamed")
        self.assertEqual(repo.config["quota_gb"], 200)
        self.assertEqual(repo.config["mount_options"], "rw,soft")
        # Mount options should be replaced, not appended.
        self.assertNotIn("ro,soft", repo.config["mount_options"])
        # No binding happened.
        self.assertFalse(repo.bind_node_id)
        self.assertNotEqual(repo.bind_node_type, Repository.BindNodeType.PROXY)

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    def test_repair_unbound_password_blank_keeps_existing(self, _sync):
        repo = self._make_unbound_nas()
        original_password = repo.config["smb_password"]
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"config": {"smb_password": ""}},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        repo.refresh_from_db()
        self.assertEqual(repo.config["smb_password"], original_password)

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    def test_repair_unbound_password_nonblank_updates(self, _sync):
        repo = self._make_unbound_nas()
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"config": {"smb_password": "new-secret"}},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        repo.refresh_from_db()
        self.assertNotIn("smb_password", repo.config)
        credential = Credential.objects.get(id=repo.credential_id)
        self.assertEqual(credential.get_secret_payload()["smb_password"], "new-secret")

    def test_repair_rejects_smb_fields_on_nfs(self):
        repo = self._make_unbound_nas(protocol=Repository.NasProtocol.NFS)
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"config": {"smb_username": "x"}},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- bind (currently unbound) ----------------------------------------

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    @mock.patch("apps.storage.services.internal.nas_repair.initialize_proxy_nas_repository")
    def test_repair_unbound_binds_proxy_and_inits_kopia(
        self, init_proxy, _sync,
    ):
        repo = self._make_unbound_nas()
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"bind_node_id": self.proxy_a.id},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        repo.refresh_from_db()
        self.assertEqual(repo.bind_node_id, self.proxy_a.id)
        self.assertEqual(repo.bind_node_type, Repository.BindNodeType.PROXY)
        self.assertEqual(repo.status, Repository.Status.CREATED)
        self.assertEqual(repo.health, Repository.Health.ONLINE)
        init_proxy.assert_called_once()

    @mock.patch("apps.storage.services.internal.nas_repair.initialize_proxy_nas_repository")
    def test_repair_unbound_rejects_existing_repository_and_restores_binding(self, initialize):
        repository = self._make_unbound_nas()
        initialize.side_effect = RepositoryAlreadyExistsError("repository already exists")

        response = self.client.patch(
            f"/api/v1/storage/repositories/{repository.id}/repair/",
            {"bind_node_id": self.proxy_a.id},
            format="json",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)
        self.assertEqual(response.data["data"]["code"], REPOSITORY_ALREADY_EXISTS_CODE)
        repository.refresh_from_db()
        self.assertIsNone(repository.bind_node_type)
        self.assertIsNone(repository.bind_node_id)
        self.assertEqual(repository.status, Repository.Status.CREATED)
        self.assertEqual(repository.health, Repository.Health.UNVERIFIED)
        self.assertNotIn("proxy_mount_path", repository.config)

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    def test_repair_unbound_bind_offline_proxy_rejected(self, _sync):
        repo = self._make_unbound_nas()
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"bind_node_id": self.proxy_offline.id},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch("apps.storage.services.internal.nas_repair.initialize_proxy_nas_repository")
    def test_repair_unbound_bind_rejected_after_backup_config_associated(self, init_proxy):
        repo = self._make_unbound_nas()
        BackupConfig.objects.create(
            organization_id=self.org.id,
            name="associated-config",
            source_type="agent",
            source_ref_id=123,
            repository_id=repo.id,
        )

        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"bind_node_id": self.proxy_a.id},
            format="json",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        repo.refresh_from_db()
        self.assertFalse(repo.bind_node_id)
        init_proxy.assert_not_called()

    # --- swap (currently bound) ------------------------------------------

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    @mock.patch("apps.storage.services.internal.nas_repair.run_agent_task_sync")
    def test_repair_bound_swap_proxy_unmounts_old(
        self, run_agent_task_sync, _sync,
    ):
        run_agent_task_sync.return_value = mock.Mock(
            task=mock.Mock(status="success", last_error=""),
            result={"mount_point": "/mnt/hfl/storage-repositories/repo-34-node-45"},
            ok=True,
        )
        repo = self._make_bound_nas()
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"bind_node_id": self.proxy_b.id},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        repo.refresh_from_db()
        self.assertEqual(repo.bind_node_id, self.proxy_b.id)
        self.assertEqual(repo.health, Repository.Health.ONLINE)
        self.assertEqual(
            repo.config["proxy_mount_path"],
            "/mnt/hfl/storage-repositories/repo-34-node-45",
        )

        # Two agent task sync calls: remount (new proxy) and unmount (old).
        kinds = [call.kwargs["kind"] for call in run_agent_task_sync.call_args_list]
        self.assertIn("repo.status", kinds)
        self.assertIn("nas.unmount", kinds)
        # Old proxy should be the node used for the unmount call.
        unmount_call = next(
            c for c in run_agent_task_sync.call_args_list
            if c.kwargs["kind"] == "nas.unmount"
        )
        self.assertEqual(unmount_call.kwargs["node_id"], self.proxy_a.id)

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    @mock.patch("apps.storage.services.internal.nas_repair.initialize_proxy_nas_repository")
    def test_repair_bound_swap_rejected_when_busy(
        self, init_proxy, _sync,
    ):
        repo = self._make_bound_nas()
        config = BackupConfig.objects.create(
            organization_id=self.org.id,
            name="busy-config",
            source_type="nas",
            source_ref_id=999,
            repository_id=repo.id,
        )
        Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="running backup",
            status=Task.Status.RUNNING,
            request_payload={"backup_config_id": config.id},
        )

        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"bind_node_id": self.proxy_b.id},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Original binding unchanged.
        repo.refresh_from_db()
        self.assertEqual(repo.bind_node_id, self.proxy_a.id)
        init_proxy.assert_not_called()

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    def test_repair_bound_swap_rejects_same_proxy(self, _sync):
        repo = self._make_bound_nas()
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"bind_node_id": self.proxy_a.id},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch("apps.storage.services.internal.nas_repair.enqueue_repository_usage_refresh")
    @mock.patch("apps.storage.services.internal.nas_repair.check_proxy_nas_repository")
    def test_repair_bound_save_only_does_not_touch_binding(
        self, check_proxy, _sync,
    ):
        repo = self._make_bound_nas()
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {
                "name": "renamed",
                "config": {"quota_gb": 250},
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        repo.refresh_from_db()
        self.assertEqual(repo.name, "renamed")
        self.assertEqual(repo.config["quota_gb"], 250)
        self.assertEqual(repo.bind_node_id, self.proxy_a.id)
        check_proxy.assert_called_once()

    def test_repair_rejects_non_nas_repo(self):
        repo = Repository.objects.create(
            organization_id=self.org.id,
            name="s3-repo",
            repo_type=Repository.Type.S3,
            s3_platform=Repository.S3Platform.AWS,
            s3_bucket="b",
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            config={},
        )
        response = self.client.patch(
            f"/api/v1/storage/repositories/{repo.id}/repair/",
            {"name": "x"},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
