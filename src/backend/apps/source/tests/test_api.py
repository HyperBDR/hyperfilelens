"""Source resource API tests."""

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
    BackupPolicy,
    BackupSourceSnapshot,
    FileFilterRule,
)
from apps.restore.models import RestorePlan
from apps.source.models import SourceBackupPipelineEntry, SourceResource
from apps.source.services.internal.agent_host_sync import sync_agent_source_host
from apps.storage.repositories.models import Repository
from apps.task.models import Task, TaskResource

MOUNTS_ROOT = agent_paths.agent_mounts_dir()


def custom_mount(leaf: str) -> str:
    return f"{MOUNTS_ROOT}/custom/{leaf}"


class SourceResourceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="source-api@test.local",
            email="source-api@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="source-test-org", name="Source Test Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.node = Node.objects.create(
            organization=self.org,
            name="proxy-1",
            role=Node.Role.PROXY,
            status=Node.Status.ONLINE,
        )
        self.client.force_authenticate(user=self.user)

    def _headers(self):
        return {"HTTP_X_ORG_KEY": self.org.key}

    def _create_backup_config_for_agent(self, agent: Node, *, name: str = "backup-config") -> BackupConfig:
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name=f"{name}-repo",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_bucket=f"{name}-bucket",
        )
        return BackupConfig.objects.create(
            organization_id=self.org.id,
            name=name,
            source_type="agent",
            source_ref_id=agent.id,
            repository_id=repository.id,
        )

    def _create_source_snapshot(
        self,
        config: BackupConfig,
        *,
        uid: str,
        status_value: str,
        task_id: int,
    ) -> BackupSourceSnapshot:
        return BackupSourceSnapshot.objects.create(
            organization_id=self.org.id,
            snapshot_uid=uid,
            idempotency_key=f"{uid}-idem",
            source_type=config.source_type,
            source_ref_id=config.source_ref_id,
            backup_config_id=config.id,
            repository_id=config.repository_id,
            task_id=task_id,
            status=status_value,
        )

    def test_create_list_statistics(self):
        create = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nfs-share-1",
                "resource_type": "nfs",
                "config": {"server": "10.0.0.1", "export_path": "/data"},
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)

        listing = self.client.get(
            "/api/v1/source/resources/",
            **self._headers(),
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(listing.data["count"], 1)

    def test_list_search_matches_nas_fields(self):
        SourceResource.objects.create(
            organization=self.org,
            name="nas-share-primary",
            resource_type="nas",
            description="Production NAS export",
            config={"server": "192.168.50.10", "share": "backup_vol"},
            bound_node=self.node,
            mount_point=custom_mount("nas-share-primary"),
        )
        SourceResource.objects.create(
            organization=self.org,
            name="other-nas",
            resource_type="nas",
            config={"server": "10.0.0.99", "share": "other"},
            bound_node=self.node,
        )

        by_server = self.client.get(
            "/api/v1/source/resources/?resource_type=nas&search=192.168.50.10",
            **self._headers(),
        )
        self.assertEqual(by_server.status_code, status.HTTP_200_OK)
        self.assertEqual(by_server.data["count"], 1)
        self.assertEqual(by_server.data["results"][0]["name"], "nas-share-primary")

        by_proxy = self.client.get(
            "/api/v1/source/resources/?resource_type=nas&search=proxy-1",
            **self._headers(),
        )
        self.assertEqual(by_proxy.status_code, status.HTTP_200_OK)
        self.assertEqual(by_proxy.data["count"], 2)

        name_field = self.client.get(
            "/api/v1/source/resources/?resource_type=nas&search=192.168.50.10&search_field=name",
            **self._headers(),
        )
        self.assertEqual(name_field.status_code, status.HTTP_200_OK)
        self.assertEqual(name_field.data["count"], 0)

        server_field = self.client.get(
            "/api/v1/source/resources/?resource_type=nas&search=192.168.50.10&search_field=server",
            **self._headers(),
        )
        self.assertEqual(server_field.status_code, status.HTTP_200_OK)
        self.assertEqual(server_field.data["count"], 1)

        stats = self.client.get(
            "/api/v1/source/resources/statistics/",
            **self._headers(),
        )
        self.assertEqual(stats.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(stats.data["total"], 1)
        self.assertIn("mounted", stats.data)
        self.assertIn("by_type", stats.data)

    def test_statistics_empty_org(self):
        resp = self.client.get(
            "/api/v1/source/resources/statistics/",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 0)

    def test_test_connection(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-local-connection",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
        )
        create = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "local-path",
                "resource_type": "local",
                "config": {"root_path": "/data"},
                "bound_node_id": agent.id,
            },
            format="json",
            **self._headers(),
        )
        rid = create.data["id"]
        resp = self.client.post(
            f"/api/v1/source/resources/{rid}/test-connection/",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])

    def test_create_nas_smb_and_nfs(self):
        smb = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-smb-1",
                "resource_type": "nas",
                "config": {
                    "protocol": "smb",
                    "server": "192.168.1.100",
                    "share": "/media",
                    "path": custom_mount("smb-media"),
                    "options": "vers=3.0,iocharset=utf8",
                },
                "credentials": {"username": "nas_user", "password": "secret"},
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(smb.status_code, status.HTTP_201_CREATED)
        self.assertEqual(smb.data["mount_point"], custom_mount("smb-media"))
        self.assertEqual(smb.data["connection_summary"], "//192.168.1.100/media")

        nfs = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-nfs-1",
                "resource_type": "nas",
                "config": {
                    "protocol": "nfs",
                    "server": "192.168.1.200",
                    "export_path": "/export/backup",
                    "path": custom_mount("nfs-export"),
                    "options": "rw,hard,intr",
                },
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(nfs.status_code, status.HTTP_201_CREATED)
        self.assertEqual(nfs.data["mount_point"], custom_mount("nfs-export"))

    def test_create_nas_normalizes_share_and_export_paths(self):
        smb = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-smb-normalized",
                "resource_type": "nas",
                "config": {
                    "protocol": "smb",
                    "server": "192.168.1.100",
                    "share": "/data",
                    "path": custom_mount("smb-data"),
                },
                "credentials": {"username": "nas_user", "password": "secret"},
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(smb.status_code, status.HTTP_201_CREATED)
        self.assertEqual(smb.data["config"]["share"], "data")
        self.assertEqual(smb.data["connection_summary"], "//192.168.1.100/data")

        nfs = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-nfs-normalized",
                "resource_type": "nas",
                "config": {
                    "protocol": "nfs",
                    "server": "192.168.1.200",
                    "export_path": "data",
                    "path": custom_mount("nfs-data"),
                },
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(nfs.status_code, status.HTTP_201_CREATED)
        self.assertEqual(nfs.data["config"]["export_path"], "/data")
        self.assertEqual(nfs.data["connection_summary"], "192.168.1.200:/data")

    def test_create_duplicate_name_rejected(self):
        payload = {
            "name": "SMB_10.147.18.31_MyShare",
            "resource_type": "nas",
            "config": {
                "protocol": "smb",
                "server": "10.147.18.31",
                "share": "MyShare",
                "path": custom_mount("smb-10.147.18.31_MyShare"),
            },
            "credentials": {"username": "root", "password": "secret"},
            "bound_node_id": self.node.id,
        }
        first = self.client.post(
            "/api/v1/source/resources/",
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        duplicate = self.client.post(
            "/api/v1/source/resources/",
            payload,
            format="json",
            **self._headers(),
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", str(duplicate.data))

    def test_create_reuses_name_after_soft_deleted_ghost_removed(self):
        ghost = SourceResource.objects.create(
            organization=self.org,
            name="SMB_10.147.18.31_MyShare",
            resource_type="nas",
            config={
                "protocol": "smb",
                "server": "10.147.18.31",
                "share": "MyShare",
                "path": custom_mount("smb-10.147.18.31_MyShare"),
            },
            bound_node=self.node,
        )
        ghost.soft_delete()

        recreate = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "SMB_10.147.18.31_MyShare",
                "resource_type": "nas",
                "config": {
                    "protocol": "smb",
                    "server": "10.147.18.31",
                    "share": "MyShare",
                    "path": custom_mount("smb-10.147.18.31_MyShare"),
                },
                "credentials": {"username": "root", "password": "secret"},
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(recreate.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            SourceResource.all_objects.filter(id=ghost.id).exists(),
        )

    @patch("apps.source.services.internal.connection.dispatch_nas_agent_task")
    def test_create_nas_auto_probes_capacity(self, mock_dispatch):
        canonical_nfs_export = custom_mount("nfs-export")
        mock_dispatch.return_value = SimpleNamespace(
            ok=True,
            timed_out=False,
            task=None,
            result={
                "mount_point": canonical_nfs_export,
                "space_info": {
                    "total_bytes": 1_000_000_000_000,
                    "used_bytes": 250_000_000_000,
                    "free_bytes": 750_000_000_000,
                },
            },
        )
        create = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-capacity-probe",
                "resource_type": "nas",
                "config": {
                    "protocol": "nfs",
                    "server": "192.168.1.50",
                    "export_path": "/export/data",
                    "path": custom_mount("nfs-export"),
                },
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        resource = SourceResource.objects.get(id=create.data["id"])
        self.assertEqual(resource.total_size, 1_000_000_000_000)
        self.assertEqual(resource.used_size, 250_000_000_000)
        self.assertEqual(resource.free_size, 750_000_000_000)
        self.assertIsNotNone(resource.last_connection_test)
        mock_dispatch.assert_called_once()

    def test_backup_selectable_catalog(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-host-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.21",
            os_name="darwin arm64",
            metadata={
                "inventory": {
                    "os": "darwin",
                    "arch": "arm64",
                    "cpu_cores": 8,
                    "memory_total_bytes": 16_000_000_000,
                    "disk_count": 2,
                }
            },
        )
        nas = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-catalog-1",
                "resource_type": "nas",
                "config": {
                    "protocol": "nfs",
                    "server": "192.168.1.50",
                    "export_path": "/export/data",
                    "path": custom_mount("nas-data"),
                },
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(nas.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SourceBackupPipelineEntry.objects.filter(
            organization=self.org,
            source_kind="nas",
            ref_id=nas.data["id"],
            step=1,
        ).exists())

        listing = self.client.get(
            "/api/v1/source/backup-selectable/?page=1&page_size=10",
            **self._headers(),
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 2)
        ids = {row["id"] for row in listing.data["results"]}
        self.assertIn(f"agent:{agent.id}", ids)
        self.assertIn(f"nas:{nas.data['id']}", ids)

        by_ids = self.client.get(
            f"/api/v1/source/backup-selectable/?ids=agent:{agent.id},nas:{nas.data['id']}",
            **self._headers(),
        )
        self.assertEqual(by_ids.status_code, status.HTTP_200_OK)
        self.assertEqual(by_ids.data["count"], 2)
        rows_by_id = {row["id"]: row for row in by_ids.data["results"]}
        agent_row = rows_by_id[f"agent:{agent.id}"]
        nas_row = rows_by_id[f"nas:{nas.data['id']}"]
        self.assertEqual(agent_row["platform"], "macos")
        self.assertEqual(agent_row["cpu_cores"], 8)
        self.assertEqual(agent_row["memory_total_bytes"], 16_000_000_000)
        self.assertEqual(agent_row["disk_count"], 2)
        self.assertEqual(nas_row["connection_uri"], "192.168.1.50:/export/data")
        self.assertNotIn("cpu_cores", nas_row)
        self.assertNotIn("memory_total_bytes", nas_row)
        self.assertNotIn("disk_count", nas_row)
        for row in by_ids.data["results"]:
            self.assertEqual(row["pipeline_step"], 1)

    def test_backup_selectable_step3_expand_includes_configured_source(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-step3-expand-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.25",
        )
        repository = Repository.objects.create(
            organization_id=self.org.id,
            name="step3-expand-repo",
            repo_type=Repository.Type.S3,
            status=Repository.Status.CREATED,
            health=Repository.Health.ONLINE,
            s3_bucket="step3-expand-bucket",
            config={"prefix": "source-a"},
        )
        policy = BackupPolicy.objects.create(
            organization_id=self.org.id,
            name="step3-expand-policy",
            schedule={"enabled": True, "cron_expr": "0 2 * * *"},
            retention={
                "enabled": True,
                "recent_points": 3,
                "hourly_enabled": True,
                "hourly_hours": 24,
                "daily_enabled": True,
                "daily_days": 7,
                "weekly_enabled": True,
                "weekly_weeks": 4,
                "monthly_enabled": True,
                "monthly_months": 12,
                "annual_enabled": True,
                "annual_years": 2,
            },
            throttling={"enabled": True, "unlimited": False, "rate_mbps": 80},
            error_handling={
                "enabled": True,
                "ignore_directory_read_errors": True,
                "ignore_file_read_errors": False,
                "ignore_unknown_entries": True,
            },
        )
        filter_rule = FileFilterRule.objects.create(
            organization_id=self.org.id,
            name="step3-expand-filter",
            ignore_patterns="*.tmp\n**/node_modules/**",
            large_file_limit_enabled=True,
            large_file_bytes_max=1024,
            ignore_cache_directories=True,
            current_filesystem_only=True,
        )
        config = BackupConfig.objects.create(
            organization_id=self.org.id,
            name="step3-expand-config",
            source_type="agent",
            source_ref_id=agent.id,
            repository_id=repository.id,
            backup_policy_id=policy.id,
            file_filter_rule_id=filter_rule.id,
            compression_level=BackupConfig.CompressionLevel.BALANCED,
        )
        BackupConfigDirectory.objects.create(
            organization_id=self.org.id,
            backup_config=config,
            path="/data",
            sort_order=0,
        )
        RestorePlan.objects.create(
            organization_id=self.org.id,
            backup_config_id=config.id,
            backup_config_dir_id=None,
            scope=RestorePlan.Scope.SNAPSHOT,
            source_type=RestorePlan.EndpointType.AGENT,
            source_ref_id=agent.id,
            source_path="",
            target_type=RestorePlan.EndpointType.AGENT,
            target_ref_id=agent.id,
            restore_dir="/restore/data",
            conflict_mode=RestorePlan.ConflictMode.SKIP,
            enabled=True,
            sort_order=0,
        )

        response = self.client.get(
            "/api/v1/source/backup-selectable/?step=3&page=1&page_size=10&expand=backup_configs,policies,runtime",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["id"], f"agent:{agent.id}")
        self.assertEqual(row["pipeline_step"], 3)
        self.assertEqual(row["backup_configs"]["count"], 1)
        self.assertEqual(row["backup_configs"]["ids"], [config.id])
        self.assertEqual(row["backup_configs"]["configs"][0]["directories"][0]["path"], "/data")
        self.assertEqual(row["backup_configs"]["configs"][0]["recovery_plans"][0]["scope"], "snapshot")
        self.assertIsNone(row["backup_configs"]["configs"][0]["recovery_plans"][0]["backup_config_dir_id"])
        self.assertEqual(row["backup_configs"]["configs"][0]["recovery_plans"][0]["source_path"], "")
        self.assertEqual(row["backup_configs"]["repos_preview"][0]["repository_id"], repository.id)
        self.assertEqual(row["backup_configs"]["repos_preview"][0]["repo_type"], repository.repo_type)
        self.assertEqual(row["policies"]["names"], ["step3-expand-policy"])
        self.assertEqual(row["filters"]["names"], ["step3-expand-filter"])
        policy_item = row["policies"]["items"][0]
        self.assertEqual(policy_item["id"], policy.id)
        self.assertEqual(policy_item["schedule"], policy.schedule)
        self.assertEqual(policy_item["retention"], policy.retention)
        self.assertEqual(policy_item["throttling"], policy.throttling)
        self.assertEqual(policy_item["error_handling"], policy.error_handling)
        self.assertEqual(policy_item["related_backup_count"], 1)
        self.assertIn("schedule_summary", policy_item)
        self.assertIn("retention_summary", policy_item)
        self.assertIsNotNone(policy_item["created_at"])
        self.assertIsNotNone(policy_item["updated_at"])
        filter_item = row["filters"]["items"][0]
        self.assertEqual(filter_item["id"], filter_rule.id)
        self.assertEqual(filter_item["ignore_patterns"], filter_rule.ignore_patterns)
        self.assertTrue(filter_item["large_file_limit_enabled"])
        self.assertEqual(filter_item["large_file_bytes_max"], 1024)
        self.assertTrue(filter_item["ignore_cache_directories"])
        self.assertTrue(filter_item["current_filesystem_only"])
        self.assertEqual(filter_item["related_backup_count"], 1)
        self.assertIn("summary", filter_item)
        self.assertIsNotNone(filter_item["created_at"])
        self.assertIsNotNone(filter_item["updated_at"])
        self.assertFalse(row["runtime"]["backup"]["running"])

    def test_backup_selectable_ids_expand_runtime_uses_requested_sources(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-runtime-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.26",
        )
        other_agent = Node.objects.create(
            organization=self.org,
            name="agent-runtime-2",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.27",
        )
        task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Backup selected source",
            status=Task.Status.RUNNING,
            trigger_type=Task.TriggerType.MANUAL,
        )
        TaskResource.objects.create(
            task=task,
            resource_type=TaskResource.Type.BACKUP_SOURCE,
            resource_subtype="agent",
            resource_id=agent.id,
        )
        other_task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Backup other source",
            status=Task.Status.RUNNING,
            trigger_type=Task.TriggerType.MANUAL,
        )
        TaskResource.objects.create(
            task=other_task,
            resource_type=TaskResource.Type.BACKUP_SOURCE,
            resource_subtype="agent",
            resource_id=other_agent.id,
        )

        response = self.client.get(
            f"/api/v1/source/backup-selectable/?ids=agent:{agent.id}&expand=runtime",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        runtime = response.data["results"][0]["runtime"]
        self.assertTrue(runtime["backup"]["running"])
        self.assertEqual(runtime["backup"]["running_count"], 1)
        self.assertEqual(runtime["backup"]["latest_task"]["id"], task.id)

    def test_backup_selectable_runtime_running_backup_ignores_historical_failure(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-runtime-history",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.28",
        )
        failed_task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Previous failed backup",
            status=Task.Status.FAILED,
            trigger_type=Task.TriggerType.MANUAL,
            progress=42,
        )
        TaskResource.objects.create(
            task=failed_task,
            resource_type=TaskResource.Type.BACKUP_SOURCE,
            resource_subtype="agent",
            resource_id=agent.id,
        )
        running_task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Current running backup",
            status=Task.Status.RUNNING,
            trigger_type=Task.TriggerType.MANUAL,
            progress=35,
        )
        TaskResource.objects.create(
            task=running_task,
            resource_type=TaskResource.Type.BACKUP_SOURCE,
            resource_subtype="agent",
            resource_id=agent.id,
        )

        response = self.client.get(
            f"/api/v1/source/backup-selectable/?ids=agent:{agent.id}&expand=runtime",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        runtime = response.data["results"][0]["runtime"]["backup"]
        self.assertTrue(runtime["running"])
        self.assertFalse(runtime["failed"])
        self.assertEqual(runtime["running_count"], 1)
        self.assertEqual(runtime["progress"], 35)
        self.assertEqual(runtime["latest_task"]["id"], running_task.id)

    def test_backup_selectable_runtime_reports_historical_restorable_snapshot(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-runtime-restorable",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.29",
        )
        config = self._create_backup_config_for_agent(agent, name="runtime-restorable-config")
        available_snapshot = self._create_source_snapshot(
            config,
            uid="runtime-restorable-available",
            status_value=BackupSourceSnapshot.Status.AVAILABLE,
            task_id=101,
        )
        creating_snapshot = self._create_source_snapshot(
            config,
            uid="runtime-restorable-creating",
            status_value=BackupSourceSnapshot.Status.CREATING,
            task_id=102,
        )
        running_task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Current running backup",
            status=Task.Status.RUNNING,
            trigger_type=Task.TriggerType.MANUAL,
            progress=12,
        )
        TaskResource.objects.create(
            task=running_task,
            resource_type=TaskResource.Type.BACKUP_SOURCE,
            resource_subtype="agent",
            resource_id=agent.id,
        )

        response = self.client.get(
            f"/api/v1/source/backup-selectable/?ids=agent:{agent.id}&expand=runtime",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        runtime = response.data["results"][0]["runtime"]
        self.assertTrue(runtime["backup"]["running"])
        self.assertEqual(runtime["latest_snapshot"]["id"], creating_snapshot.id)
        self.assertFalse(runtime["latest_snapshot"]["recoverable"])
        self.assertTrue(runtime["has_restorable_snapshot"])
        self.assertEqual(runtime["restorable_snapshot_count"], 1)
        self.assertEqual(runtime["latest_restorable_snapshot"]["id"], available_snapshot.id)
        self.assertTrue(runtime["latest_restorable_snapshot"]["recoverable"])

    def test_backup_selectable_runtime_restorable_snapshot_boundaries(self):
        partial_agent = Node.objects.create(
            organization=self.org,
            name="agent-runtime-partial",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.30",
        )
        failed_agent = Node.objects.create(
            organization=self.org,
            name="agent-runtime-failed-only",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.31",
        )
        empty_agent = Node.objects.create(
            organization=self.org,
            name="agent-runtime-empty",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.32",
        )
        partial_config = self._create_backup_config_for_agent(partial_agent, name="runtime-partial-config")
        failed_config = self._create_backup_config_for_agent(failed_agent, name="runtime-failed-config")
        partial_snapshot = self._create_source_snapshot(
            partial_config,
            uid="runtime-restorable-partial",
            status_value=BackupSourceSnapshot.Status.PARTIAL,
            task_id=201,
        )
        self._create_source_snapshot(
            failed_config,
            uid="runtime-non-restorable-failed",
            status_value=BackupSourceSnapshot.Status.FAILED,
            task_id=202,
        )

        response = self.client.get(
            (
                "/api/v1/source/backup-selectable/?"
                f"ids=agent:{partial_agent.id},agent:{failed_agent.id},agent:{empty_agent.id}&expand=runtime"
            ),
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows_by_id = {row["id"]: row for row in response.data["results"]}
        partial_runtime = rows_by_id[f"agent:{partial_agent.id}"]["runtime"]
        failed_runtime = rows_by_id[f"agent:{failed_agent.id}"]["runtime"]
        empty_runtime = rows_by_id[f"agent:{empty_agent.id}"]["runtime"]
        self.assertTrue(partial_runtime["has_restorable_snapshot"])
        self.assertEqual(partial_runtime["restorable_snapshot_count"], 1)
        self.assertEqual(partial_runtime["latest_restorable_snapshot"]["id"], partial_snapshot.id)
        self.assertFalse(failed_runtime["has_restorable_snapshot"])
        self.assertEqual(failed_runtime["restorable_snapshot_count"], 0)
        self.assertIsNone(failed_runtime["latest_restorable_snapshot"])
        self.assertFalse(empty_runtime["has_restorable_snapshot"])
        self.assertEqual(empty_runtime["restorable_snapshot_count"], 0)
        self.assertIsNone(empty_runtime["latest_restorable_snapshot"])

    def test_sync_agent_source_host_normalizes_darwin_platform(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-mac-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            os_name="darwin arm64",
            metadata={"inventory": {"os": "darwin", "arch": "arm64"}},
        )

        resource = sync_agent_source_host(node=agent)

        self.assertIsNotNone(resource)
        self.assertEqual(resource.config["platform"], "macos")

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_agent_directory_uses_agent_task(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-dir-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.41",
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-agent-dir",
            result={
                "entries": [
                    {"name": "data", "path": "/data", "is_dir": True, "size": 0},
                    {"name": "README", "path": "/README", "is_dir": False, "size": 12},
                ]
            },
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=agent:{agent.id}&path=/",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["source_id"], f"agent:{agent.id}")
        self.assertEqual(resp.data["root"]["path"], "/")
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["entries"][0]["path"], "/data")
        self.assertEqual(resp.data["entries"][0]["path_type"], "directory")
        mock_run_task.assert_called_once()
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["node_id"], agent.id)
        self.assertEqual(kwargs["kind"], "explorer.list")
        self.assertEqual(kwargs["payload"], {
            "path": "/",
            "list_mounts": False,
            "dirs_only": True,
            "include_metadata": False,
            "limit": 200,
        })

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_agent_directory_can_include_files(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-file-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.43",
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-agent-file",
            result={
                "entries": [
                    {"name": "data", "path": "/data", "is_dir": True, "size": 0},
                    {"name": "README", "path": "/README", "is_dir": False, "size": 12},
                ]
            },
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=agent:{agent.id}&path=/&include_files=true",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 2)
        self.assertEqual(
            [(entry["path"], entry["path_type"], entry["isLeaf"]) for entry in resp.data["entries"]],
            [("/data", "directory", False), ("/README", "file", True)],
        )
        mock_run_task.assert_called_once()
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["payload"], {
            "path": "/",
            "list_mounts": False,
            "dirs_only": False,
            "include_metadata": True,
            "limit": 200,
        })

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_agent_directory_normalizes_type_fields(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-type-fields-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.45",
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-agent-type-fields",
            result={
                "entries": [
                    {"name": "bin", "path": "/bin", "is_dir": False, "path_type": "directory"},
                    {"name": "opt", "path": "/opt", "type": "dir"},
                    {"name": "var", "path": "/var", "mode": "drwxr-xr-x"},
                    {"name": "README", "path": "/README", "path_type": "file"},
                ]
            },
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=agent:{agent.id}&path=/",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 3)
        self.assertEqual(
            [(entry["path"], entry["path_type"], entry["is_dir"], entry["isLeaf"]) for entry in resp.data["entries"]],
            [
                ("/bin", "directory", True, False),
                ("/opt", "directory", True, False),
                ("/var", "directory", True, False),
            ],
        )

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_path_info_validates_manual_file_path(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-path-info",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.44",
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            result={
                "name": "report.txt",
                "path": "/data/report.txt",
                "exists": True,
                "is_dir": False,
                "path_type": "file",
                "size": 42,
                "mod_time": "2026-06-24T01:02:03Z",
            },
            task=SimpleNamespace(id="task-path-info", last_error="", status="success"),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/path-info/?source_id=agent:{agent.id}&path=/data/report.txt",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["path"], "/data/report.txt")
        self.assertEqual(resp.data["path_type"], "file")
        self.assertFalse(resp.data["is_dir"])
        self.assertTrue(resp.data["isLeaf"])
        mock_run_task.assert_called_once()
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["kind"], "path.info")
        self.assertEqual(kwargs["payload"], {"path": "/data/report.txt"})

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_path_info_can_skip_metadata(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-path-info-lite",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.46",
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            result={
                "name": "tmp",
                "path": "/tmp",
                "exists": True,
                "is_dir": True,
                "path_type": "directory",
                "size": 4096,
                "mod_time": "2026-06-24T01:02:03Z",
            },
            task=SimpleNamespace(id="task-path-info-lite", last_error="", status="success"),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/path-info/?source_id=agent:{agent.id}&path=/tmp&include_metadata=false",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["path"], "/tmp")
        self.assertEqual(resp.data["path_type"], "directory")
        self.assertNotIn("size", resp.data)
        self.assertNotIn("mod_time", resp.data)
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["payload"], {"path": "/tmp", "include_metadata": False})

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_agent_directory_root_uses_mount_listing(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-dir-root",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.42",
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-agent-dir-root",
            result={
                "entries": [
                    {"name": "/", "path": "/", "is_dir": True, "size": 0},
                    {"name": "home", "path": "/home", "is_dir": True, "size": 0},
                ]
            },
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=agent:{agent.id}",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_run_task.assert_called_once()
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["payload"], {
            "path": "",
            "list_mounts": True,
            "dirs_only": True,
            "include_metadata": False,
            "limit": 200,
        })

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_agent_directory_root_include_files_stays_lightweight(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-dir-root-files",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.45",
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-agent-dir-root-files",
            result={"entries": [{"name": "/", "path": "/", "is_dir": True, "size": 0}]},
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=agent:{agent.id}&include_files=true&limit=500",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["payload"], {
            "path": "",
            "list_mounts": True,
            "dirs_only": True,
            "include_metadata": False,
            "limit": 500,
        })

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_proxy_directory_uses_proxy_task(self, mock_run_task):
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-proxy-dir",
            result={
                "entries": [
                    {"name": "repos", "path": "/repos", "is_dir": True, "size": 0},
                ]
            },
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=proxy:{self.node.id}&path=/",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["source_id"], f"proxy:{self.node.id}")
        self.assertEqual(resp.data["source_kind"], "proxy")
        self.assertEqual(resp.data["entries"][0]["path"], "/repos")
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["node_id"], self.node.id)
        self.assertEqual(kwargs["payload"], {
            "path": "/",
            "list_mounts": False,
            "dirs_only": True,
            "include_metadata": False,
            "limit": 200,
        })

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_nas_directory_uses_proxy_mount_only(self, mock_run_task):
        create = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-dir-1",
                "resource_type": "nas",
                "config": {
                    "protocol": "nfs",
                    "server": "192.168.1.60",
                    "export_path": "/export/data",
                    "path": custom_mount("nas-data"),
                },
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        resource = SourceResource.objects.get(id=create.data["id"])
        root_path = custom_mount("nas-data")

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=nas:{resource.id}",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["root_path"], "/")
        self.assertEqual(resp.data["mount_path"], root_path)
        self.assertEqual(resp.data["root"]["path"], "/")
        self.assertEqual(resp.data["root"]["label"], "/export/data")
        self.assertEqual(resp.data["entries"], [])
        mock_run_task.assert_not_called()

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_nas_directory_lists_share_relative_children(self, mock_run_task):
        create = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-dir-children",
                "resource_type": "nas",
                "config": {
                    "protocol": "nfs",
                    "server": "192.168.1.60",
                    "export_path": "/export/data",
                    "path": custom_mount("nas-data"),
                },
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        resource = SourceResource.objects.get(id=create.data["id"])
        root_path = custom_mount("nas-data")

        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-nas-dir",
            result={
                "entries": [
                    {
                        "name": "projects",
                        "path": f"{root_path}/projects",
                        "is_dir": True,
                        "size": 0,
                    },
                    {"name": "leak", "path": "/tmp/leak", "is_dir": True, "size": 0},
                    {
                        "name": "note.txt",
                        "path": f"{root_path}/note.txt",
                        "is_dir": False,
                        "size": 9,
                    },
                ]
            },
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=nas:{resource.id}&path=/&include_files=true&include_metadata=false",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["root_path"], "/")
        self.assertEqual(resp.data["mount_path"], root_path)
        self.assertEqual(resp.data["path"], "/")
        self.assertEqual(
            [(entry["path"], entry["path_type"], entry["isLeaf"]) for entry in resp.data["entries"]],
            [
                ("/projects", "directory", False),
                ("/note.txt", "file", True),
            ],
        )
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["node_id"], self.node.id)
        payload = kwargs["payload"]
        self.assertEqual(payload["path"], root_path)
        self.assertEqual(payload["list_mounts"], False)
        self.assertEqual(payload["dirs_only"], False)
        self.assertEqual(payload["include_metadata"], False)
        self.assertEqual(payload["limit"], 200)
        self.assertIn("nas", payload)
        self.assertEqual(payload["nas"]["server"], "192.168.1.60")
        self.assertEqual(payload["nas"]["mount_point"], root_path)

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_directory_limit_and_has_more(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-dir-limit",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-agent-dir-limit",
            result={
                "has_more": True,
                "next_cursor": "1",
                "entries": [
                    {"name": "a", "path": "/a", "is_dir": True},
                ],
            },
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=agent:{agent.id}&path=/&limit=1",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["has_more"])
        self.assertEqual(resp.data["next_cursor"], "1")
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["payload"], {
            "path": "/",
            "list_mounts": False,
            "dirs_only": True,
            "include_metadata": False,
            "limit": 1,
        })

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_directory_cursor_is_forwarded(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-dir-cursor",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
        )
        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-agent-dir-cursor",
            result={"entries": []},
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=agent:{agent.id}&path=/data&limit=500&cursor=500&include_files=true&include_metadata=false",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        _, kwargs = mock_run_task.call_args
        self.assertEqual(kwargs["payload"], {
            "path": "/data",
            "list_mounts": False,
            "dirs_only": False,
            "include_metadata": False,
            "limit": 500,
            "cursor": "500",
        })

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_nas_directory_dispatches_agent_without_mount_status(self, mock_run_task):
        create = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "nas-unmounted-1",
                "resource_type": "nas",
                "config": {
                    "protocol": "nfs",
                    "server": "192.168.1.61",
                    "export_path": "/export/data",
                    "path": custom_mount("unmounted"),
                },
                "bound_node_id": self.node.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)

        mock_run_task.return_value = SimpleNamespace(
            timed_out=False,
            ok=True,
            task_id="task-nas-unmounted",
            result={"entries": []},
            task=SimpleNamespace(last_error=""),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=nas:{create.data['id']}&path=/",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_run_task.assert_called_once()
        payload = mock_run_task.call_args.kwargs["payload"]
        self.assertIn("nas", payload)
        self.assertEqual(payload["nas"]["export_path"], "/export/data")

    @patch("apps.source.services.internal.backup_source_directory.run_agent_task_sync")
    def test_backup_selectable_nas_directory_requires_proxy_binding(self, mock_run_task):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-for-nas",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
        )
        resource = SourceResource.objects.create(
            organization=self.org,
            name="nas-agent-bound",
            resource_type="nas",
            config={"protocol": "nfs", "server": "192.168.1.62", "export_path": "/export/data"},
            bound_node=agent,
            mount_status="mounted",
            mount_point=custom_mount("agent-bound"),
        )

        resp = self.client.get(
            f"/api/v1/source/backup-selectable/directories/?source_id=nas:{resource.id}",
            **self._headers(),
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        problem = resp.data["data"]
        self.assertEqual(problem["code"], "VALIDATION.FAILED")
        self.assertIn("proxy node", str(problem["errors"]).lower())
        mock_run_task.assert_not_called()

    def test_backup_selectable_pipeline_steps(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-pipeline-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.31",
        )
        sync_agent_source_host(node=agent)
        agent_key = f"agent:{agent.id}"
        self.assertTrue(SourceBackupPipelineEntry.objects.filter(
            organization=self.org,
            source_kind="agent",
            ref_id=agent.id,
            step=1,
        ).exists())

        step1 = self.client.get(
            "/api/v1/source/backup-selectable/?step=1&page=1&page_size=10",
            **self._headers(),
        )
        self.assertEqual(step1.status_code, status.HTTP_200_OK)
        self.assertIn(agent_key, {row["id"] for row in step1.data["results"]})

        advance = self.client.post(
            "/api/v1/source/backup-selectable/pipeline/",
            {"ids": [agent_key], "step": 2},
            format="json",
            **self._headers(),
        )
        self.assertEqual(advance.status_code, status.HTTP_200_OK)
        self.assertEqual(advance.data["updated"], [agent_key])

        step1_after = self.client.get(
            "/api/v1/source/backup-selectable/?step=1&page=1&page_size=10",
            **self._headers(),
        )
        self.assertEqual(step1_after.status_code, status.HTTP_200_OK)
        self.assertNotIn(agent_key, {row["id"] for row in step1_after.data["results"]})

        step2 = self.client.get(
            "/api/v1/source/backup-selectable/?step=2&page=1&page_size=10",
            **self._headers(),
        )
        self.assertEqual(step2.status_code, status.HTTP_200_OK)
        matched = [row for row in step2.data["results"] if row["id"] == agent_key]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["pipeline_step"], 2)

        advance_ready = self.client.post(
            "/api/v1/source/backup-selectable/pipeline/",
            {"ids": [agent_key], "step": 3},
            format="json",
            **self._headers(),
        )
        self.assertEqual(advance_ready.status_code, status.HTTP_400_BAD_REQUEST)

        revert = self.client.post(
            "/api/v1/source/backup-selectable/pipeline/",
            {"ids": [agent_key], "step": 1},
            format="json",
            **self._headers(),
        )
        self.assertEqual(revert.status_code, status.HTTP_400_BAD_REQUEST)

        step1_not_restored = self.client.get(
            "/api/v1/source/backup-selectable/?step=1&page=1&page_size=10",
            **self._headers(),
        )
        self.assertNotIn(agent_key, {row["id"] for row in step1_not_restored.data["results"]})

    def test_backup_selectable_pipeline_revert_step2_to_step1(self):
        agent = Node.objects.create(
            organization=self.org,
            name="agent-pipeline-revert-1",
            role=Node.Role.AGENT,
            status=Node.Status.ONLINE,
            ip_address="10.0.0.32",
        )
        sync_agent_source_host(node=agent)
        agent_key = f"agent:{agent.id}"
        source_host = SourceResource.objects.get(bound_node=agent, resource_type="local")

        advance = self.client.post(
            "/api/v1/source/backup-selectable/pipeline/",
            {"ids": [agent_key], "step": 2},
            format="json",
            **self._headers(),
        )
        self.assertEqual(advance.status_code, status.HTTP_200_OK)

        revert = self.client.post(
            "/api/v1/source/backup-selectable/pipeline/revert/",
            {"ids": [agent_key], "target_step": 1},
            format="json",
            **self._headers(),
        )
        self.assertEqual(revert.status_code, status.HTTP_200_OK)
        self.assertEqual(revert.data["updated"], [agent_key])
        agent.refresh_from_db()
        source_host.refresh_from_db()
        self.assertFalse(agent.is_deleted)
        self.assertFalse(source_host.is_deleted)
        self.assertFalse(
            SourceBackupPipelineEntry.objects.filter(
                organization=self.org,
                source_kind="agent",
                ref_id=agent.id,
            ).exists()
        )

        step1 = self.client.get(
            "/api/v1/source/backup-selectable/?step=1&page=1&page_size=10",
            **self._headers(),
        )
        self.assertIn(agent_key, {row["id"] for row in step1.data["results"]})

        step2 = self.client.get(
            "/api/v1/source/backup-selectable/?step=2&page=1&page_size=10",
            **self._headers(),
        )
        self.assertNotIn(agent_key, {row["id"] for row in step2.data["results"]})


@override_settings(SOURCE_UNREGISTER_EAGER=True)
class BackupSourceBulkDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="bulk-delete@test.local",
            email="bulk-delete@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="bulk-delete-org", name="Bulk Delete Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.agent = Node.objects.create(
            organization=self.org,
            name="agent-offline-1",
            role=Node.Role.AGENT,
            status=Node.Status.OFFLINE,
        )
        self.client.force_authenticate(user=self.user)

    def _headers(self):
        return {"HTTP_X_ORG_KEY": self.org.key}

    def test_delete_preflight_flags_offline_agent(self):
        agent_key = f"agent:{self.agent.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/delete-preflight/",
            {"ids": [agent_key]},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["strict_may_fail"])
        self.assertTrue(any(row["code"] == "agent_offline" for row in response.data["risks"]))

    def test_delete_preflight_flags_proxy_unbound_for_needs_proxy_nas(self):
        resource = SourceResource.objects.create(
            organization=self.org,
            name="needs-proxy-nas",
            resource_type="nas",
            config={"protocol": "nfs", "server": "192.168.99.11", "export_path": "/data2"},
            mount_status="unmounted",
            status_message="needs_proxy",
        )
        nas_key = f"nas:{resource.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/delete-preflight/",
            {"ids": [nas_key]},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["strict_may_fail"])
        self.assertTrue(any(row["code"] == "proxy_unbound" for row in response.data["risks"]))

    def test_bulk_delete_requires_exact_unregister_confirmation(self):
        agent_key = f"agent:{self.agent.id}"
        for confirmation in ("unregister", "UNREGISTER ", " UNREGISTER"):
            with self.subTest(confirmation=confirmation):
                response = self.client.post(
                    "/api/v1/source/backup-selectable/bulk-delete/",
                    {"ids": [agent_key], "force": True, "confirmation": confirmation},
                    format="json",
                    **self._headers(),
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("confirmation", response.data)
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.is_deleted)

    def test_bulk_delete_strict_fails_for_offline_agent(self):
        agent_key = f"agent:{self.agent.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/bulk-delete/",
            {"ids": [agent_key], "force": False, "confirmation": "UNREGISTER"},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("reasons", response.data)
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.is_deleted)
        self.assertEqual(Task.objects.filter(task_type=Task.Type.SOURCE_UNREGISTER).count(), 0)

    def test_bulk_delete_422_wraps_reasons_in_problem_meta(self):
        agent_key = f"agent:{self.agent.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/bulk-delete/",
            {"ids": [agent_key], "force": False, "confirmation": "UNREGISTER"},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        payload = response.data.get("data") if isinstance(response.data, dict) else {}
        if isinstance(payload, dict) and isinstance(payload.get("meta"), dict):
            self.assertTrue(payload["meta"].get("reasons"))
            self.assertTrue(payload["meta"].get("hint"))
        else:
            self.assertIn("reasons", response.data)

    @patch("apps.source.services.internal.backup_source_delete._delete_repository_snapshots")
    @patch("apps.source.services.internal.backup_source_delete._purge_protection_db")
    @patch("apps.source.services.internal.backup_source_delete._mark_tasks_orphaned")
    def test_bulk_delete_force_succeeds_for_offline_agent(
        self,
        mock_orphan,
        mock_purge,
        mock_snapshots,
    ):
        mock_snapshots.return_value = {
            "snapshots_purged": 0,
            "repository_blobs_deleted": 0,
            "repository_purge_pending": 0,
        }
        mock_purge.return_value = {
            "backup_configs_removed": 0,
            "snapshots_removed": 0,
            "restore_plans_removed": 0,
            "restore_records_removed": 0,
        }
        mock_orphan.return_value = 0

        agent_key = f"agent:{self.agent.id}"
        response = self.client.post(
            "/api/v1/source/backup-selectable/bulk-delete/",
            {"ids": [agent_key], "force": True, "confirmation": "UNREGISTER"},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data["ok"])
        self.assertEqual(response.data["task_uuid"], str(Task.objects.get(task_type=Task.Type.SOURCE_UNREGISTER).task_uuid))
        self.assertEqual(response.data["task_uuids"], [response.data["task_uuid"]])
        task = Task.objects.get(task_type=Task.Type.SOURCE_UNREGISTER)
        self.assertTrue(task.resources.get().is_primary)
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.is_deleted)

    @patch("apps.source.services.internal.backup_source_delete._delete_repository_snapshots")
    @patch("apps.source.services.internal.backup_source_delete._purge_protection_db")
    @patch("apps.source.services.internal.backup_source_delete._mark_tasks_orphaned")
    def test_bulk_delete_creates_one_primary_task_per_source(
        self,
        mock_orphan,
        mock_purge,
        mock_snapshots,
    ):
        mock_snapshots.return_value = {
            "snapshots_purged": 0,
            "repository_blobs_deleted": 0,
            "repository_purge_pending": 0,
        }
        mock_purge.return_value = {
            "backup_configs_removed": 0,
            "snapshots_removed": 0,
            "restore_plans_removed": 0,
            "restore_records_removed": 0,
        }
        mock_orphan.return_value = 0
        second_agent = Node.objects.create(
            organization=self.org,
            name="agent-offline-2",
            role=Node.Role.AGENT,
            status=Node.Status.OFFLINE,
        )

        response = self.client.post(
            "/api/v1/source/backup-selectable/bulk-delete/",
            {
                "ids": [f"agent:{self.agent.id}", f"agent:{second_agent.id}"],
                "force": True,
                "confirmation": "UNREGISTER",
            },
            format="json",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        self.assertEqual(len(response.data["task_uuids"]), 2)
        tasks = Task.objects.filter(task_type=Task.Type.SOURCE_UNREGISTER).order_by("id")
        self.assertEqual(tasks.count(), 2)
        self.assertTrue(all(task.resources.count() == 1 and task.resources.get().is_primary for task in tasks))

    @patch("apps.source.services.internal.backup_source_delete._strict_nas_umount")
    @patch("apps.source.services.internal.backup_source_delete._delete_repository_snapshots")
    @patch("apps.source.services.internal.backup_source_delete._purge_protection_db")
    @patch("apps.source.services.internal.backup_source_delete._mark_tasks_orphaned")
    def test_nas_bulk_delete_hard_deletes_and_allows_recreate(
        self,
        mock_orphan,
        mock_purge,
        mock_snapshots,
        mock_umount,
    ):
        mock_umount.return_value = {"skipped": True}
        mock_snapshots.return_value = {
            "snapshots_purged": 0,
            "repository_blobs_deleted": 0,
            "repository_purge_pending": 0,
        }
        mock_purge.return_value = {
            "backup_configs_removed": 0,
            "snapshots_removed": 0,
            "restore_plans_removed": 0,
            "restore_records_removed": 0,
        }
        mock_orphan.return_value = 0

        proxy = Node.objects.create(
            organization=self.org,
            name="proxy-nas-delete",
            role=Node.Role.PROXY,
            status=Node.Status.ONLINE,
        )
        resource = SourceResource.objects.create(
            organization=self.org,
            name="SMB_10.147.18.31_MyShare",
            resource_type="nas",
            config={
                "protocol": "smb",
                "server": "10.147.18.31",
                "share": "MyShare",
                "path": custom_mount("smb-10.147.18.31_MyShare"),
            },
            bound_node=proxy,
        )
        nas_key = f"nas:{resource.id}"

        delete_resp = self.client.post(
            "/api/v1/source/backup-selectable/bulk-delete/",
            {"ids": [nas_key], "force": False, "confirmation": "UNREGISTER"},
            format="json",
            **self._headers(),
        )
        self.assertEqual(delete_resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(delete_resp.data["ok"])
        task = Task.objects.get(task_type=Task.Type.SOURCE_UNREGISTER)
        self.assertEqual(task.status, Task.Status.SUCCESS)
        self.assertTrue(
            TaskResource.objects.filter(
                task=task,
                resource_type=TaskResource.Type.BACKUP_SOURCE,
                resource_subtype="nas",
                resource_id=resource.id,
            ).exists()
        )
        self.assertFalse(SourceResource.all_objects.filter(id=resource.id).exists())

        recreate = self.client.post(
            "/api/v1/source/resources/",
            {
                "name": "SMB_10.147.18.31_MyShare",
                "resource_type": "nas",
                "config": {
                    "protocol": "smb",
                    "server": "10.147.18.31",
                    "share": "MyShare",
                    "path": custom_mount("smb-10.147.18.31_MyShare"),
                },
                "credentials": {"username": "root", "password": "secret"},
                "bound_node_id": proxy.id,
            },
            format="json",
            **self._headers(),
        )
        self.assertEqual(recreate.status_code, status.HTTP_201_CREATED)

    def test_bulk_delete_removes_source_nas_record(self):
        resource = SourceResource.objects.create(
            organization=self.org,
            name="delete-nas-record",
            resource_type="nas",
            config={"protocol": "nfs", "server": "192.168.10.20", "export_path": "/data"},
            mount_status="unmounted",
        )
        nas_key = f"nas:{resource.id}"

        response = self.client.post(
            "/api/v1/source/backup-selectable/bulk-delete/",
            {"ids": [nas_key], "force": False, "confirmation": "UNREGISTER"},
            format="json",
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        self.assertIn(nas_key, response.data["deleted"])
        task = Task.objects.get(task_type=Task.Type.SOURCE_UNREGISTER)
        self.assertEqual(task.status, Task.Status.SUCCESS)
        self.assertTrue(
            TaskResource.objects.filter(
                task=task,
                resource_type=TaskResource.Type.BACKUP_SOURCE,
                resource_subtype="nas",
                resource_id=resource.id,
            ).exists()
        )
        self.assertFalse(SourceResource.all_objects.filter(id=resource.id).exists())
        self.assertFalse(
            SourceBackupPipelineEntry.objects.filter(
                organization=self.org,
                source_kind="nas",
                ref_id=resource.id,
            ).exists()
        )


class SourceUnregisterCeleryTests(TestCase):
    def test_execute_source_unregister_task_is_celery_registered(self):
        import apps.source.tasks  # noqa: F401
        from common.celery import app as celery_app

        self.assertIn(
            "apps.source.tasks.source_unregister.execute_source_unregister_task",
            celery_app.tasks,
        )

    def test_reconcile_stuck_source_unregister_tasks_task_is_celery_registered(self):
        import apps.source.tasks  # noqa: F401
        from common.celery import app as celery_app

        self.assertIn(
            "apps.source.tasks.source_unregister.reconcile_stuck_source_unregister_tasks_task",
            celery_app.tasks,
        )
