from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from apps.iam.models import Organization
from apps.node.models import Node
from apps.source.models import SourceResource
from apps.source.services.interface import (
    bind_node,
    test_resource_connection,
    update_source_resource,
)
from apps.source.tasks.connection_probe import (
    reconcile_stale_source_connection_probes,
    run_source_resource_capacity_probe,
)


class SourceConnectionProbeTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            key="source-connection-probe-org",
            name="Source Connection Probe Org",
        )
        self.proxy = Node.objects.create(
            organization=self.org,
            name="source-connection-proxy",
            role=Node.Role.PROXY,
            status=Node.Status.ONLINE,
        )
        self.probe_token = uuid4()
        self.resource = SourceResource.objects.create(
            organization=self.org,
            name="source-connection-nas",
            resource_type="nas",
            config={
                "protocol": "nfs",
                "server": "192.0.2.20",
                "export_path": "/source",
            },
            bound_node=self.proxy,
            connection_test_status="pending",
            connection_probe_token=self.probe_token,
        )

    @mock.patch("apps.source.tasks.connection_probe.run_connection_test")
    def test_probe_applies_capacity_for_current_source_revision(self, run_test):
        run_test.return_value = {
            "success": True,
            "message": "Connection test successful",
            "details": {
                "mount_point": "/var/lib/hyperfilelens-agent/mounts/custom/source",
                "space_info": {
                    "total_bytes": 1000,
                    "used_bytes": 400,
                    "free_bytes": 600,
                },
            },
        }

        result = run_source_resource_capacity_probe(
            resource_id=self.resource.id,
            probe_token=str(self.probe_token),
            expected_bound_node_id=self.proxy.id,
        )

        self.resource.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.resource.total_size, 1000)
        self.assertEqual(self.resource.used_size, 400)
        self.assertEqual(self.resource.free_size, 600)
        self.assertIsNotNone(self.resource.last_connection_test)

    @mock.patch("apps.source.tasks.connection_probe.run_connection_test")
    def test_probe_discards_result_after_source_edit(self, run_test):
        def edit_source(**_kwargs):
            update_source_resource(
                resource=SourceResource.objects.get(pk=self.resource.id),
                user=None,
                description="edited while probe was running",
            )
            return {
                "success": True,
                "message": "Connection test successful",
                "details": {
                    "space_info": {
                        "total_bytes": 1000,
                        "used_bytes": 400,
                        "free_bytes": 600,
                    }
                },
            }

        run_test.side_effect = edit_source

        result = run_source_resource_capacity_probe(
            resource_id=self.resource.id,
            probe_token=str(self.probe_token),
            expected_bound_node_id=self.proxy.id,
        )

        self.resource.refresh_from_db()
        self.assertEqual(
            result,
            {"status": "discarded", "reason": "source_changed"},
        )
        self.assertEqual(self.resource.total_size, 0)
        self.assertIsNone(self.resource.last_connection_test)

    @mock.patch("apps.source.tasks.connection_probe.run_connection_test")
    def test_probe_discards_result_after_source_delete(self, run_test):
        def delete_source(**_kwargs):
            SourceResource.objects.get(pk=self.resource.id).soft_delete()
            return {"success": True, "message": "Connection test successful"}

        run_test.side_effect = delete_source

        result = run_source_resource_capacity_probe(
            resource_id=self.resource.id,
            probe_token=str(self.probe_token),
            expected_bound_node_id=self.proxy.id,
        )

        deleted = SourceResource.all_objects.get(pk=self.resource.id)
        self.assertEqual(
            result,
            {"status": "discarded", "reason": "source_deleted"},
        )
        self.assertTrue(deleted.is_deleted)
        self.assertEqual(deleted.total_size, 0)

    @mock.patch("apps.source.tasks.connection_probe.run_connection_test")
    def test_probe_skips_when_proxy_is_offline(self, run_test):
        self.proxy.status = Node.Status.OFFLINE
        self.proxy.save(update_fields=["status", "updated_at"])

        result = run_source_resource_capacity_probe(
            resource_id=self.resource.id,
            probe_token=str(self.probe_token),
            expected_bound_node_id=self.proxy.id,
        )

        self.assertEqual(result, {"status": "failed", "reason": "proxy_offline"})
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.connection_test_status, "failed")
        run_test.assert_not_called()

    def test_reconcile_fails_stale_probe_and_clears_token(self):
        SourceResource.objects.filter(pk=self.resource.id).update(
            updated_at=timezone.now() - timedelta(minutes=20),
        )

        result = reconcile_stale_source_connection_probes()

        self.resource.refresh_from_db()
        self.assertEqual(result, {"stale": 1, "failed": 1})
        self.assertEqual(self.resource.connection_test_status, "failed")
        self.assertIsNone(self.resource.connection_probe_token)
        self.assertEqual(self.resource.status, "error")

    @mock.patch("apps.source.services.interface.schedule_remount_after_proxy_change")
    def test_bind_node_cancels_active_probe_immediately(self, schedule_remount):
        replacement = Node.objects.create(
            organization=self.org,
            name="source-connection-replacement-proxy",
            role=Node.Role.PROXY,
            status=Node.Status.ONLINE,
        )

        result = bind_node(resource=self.resource, node_id=replacement.id)

        self.resource.refresh_from_db()
        self.assertTrue(result["success"])
        self.assertEqual(self.resource.bound_node_id, replacement.id)
        self.assertEqual(self.resource.connection_test_status, "idle")
        self.assertIsNone(self.resource.connection_probe_token)
        schedule_remount.assert_called_once()

    @mock.patch("apps.source.services.interface.run_connection_test")
    def test_manual_probe_discards_result_after_source_edit(self, run_test):
        def edit_source(**_kwargs):
            update_source_resource(
                resource=SourceResource.objects.get(pk=self.resource.id),
                user=None,
                description="edited during manual probe",
            )
            return {"success": True, "message": "Connection test successful"}

        run_test.side_effect = edit_source

        result = test_resource_connection(resource=self.resource)

        self.resource.refresh_from_db()
        self.assertTrue(result["stale"])
        self.assertEqual(self.resource.description, "edited during manual probe")
        self.assertEqual(self.resource.connection_test_status, "idle")
        self.assertIsNone(self.resource.last_connection_test)
