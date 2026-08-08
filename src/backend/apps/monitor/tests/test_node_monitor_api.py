"""Node monitor ingest (Host) and community read-API gating."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.monitor.models import ResourceMetric
from apps.monitor.services.internal.node_metrics import ingest_node_monitor_sample
from apps.node.models import Node
from apps.node.models.base import NodeRole
from common.extension_loader import extensions_enabled


class NodeMonitorIngestTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="node-monitor-org", name="Node Monitor Org")
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-01",
            role=NodeRole.AGENT,
            status=Node.Status.ACTIVE,
            availability=Node.Availability.ONLINE,
            metadata={"inventory": {"hostname": "agent-host", "os": "linux", "arch": "amd64"}},
        )

    def test_ingest_persists_resource_metric(self):
        ingest_node_monitor_sample(
            node=self.node,
            sample={
                "cpu": {"usage_percent": 9.0, "logical_cores": 2},
                "memory": {"percent": 33.0, "total": 100, "available": 67},
                "disks": [{"mountpoint": "/"}, {"mountpoint": "/data"}],
                "networks": [{"bytes_recv": 10, "bytes_sent": 20}],
            },
        )
        row = ResourceMetric.objects.filter(resource_id=str(self.node.id)).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.metrics.get("cpu_usage"), 9.0)
        self.assertEqual(row.metrics.get("memory_usage"), 33.0)
        self.node.refresh_from_db()
        inv = (self.node.metadata or {}).get("inventory") or {}
        self.assertEqual(inv.get("cpu_cores"), 2)
        self.assertEqual(inv.get("memory_total_bytes"), 100)
        self.assertEqual(inv.get("disk_count"), 2)

    def test_ingest_sums_disk_capacity_across_volumes(self):
        ingest_node_monitor_sample(
            node=self.node,
            sample={
                "cpu": {"logical_cores": 4},
                "disks": [
                    {
                        "mountpoint": "C:",
                        "total": 500_000_000_000,
                        "used": 200_000_000_000,
                        "free": 300_000_000_000,
                    },
                    {
                        "mountpoint": "D:\\",
                        "total": 1_000_000_000_000,
                        "used": 400_000_000_000,
                        "free": 600_000_000_000,
                    },
                ],
            },
        )
        self.node.refresh_from_db()
        inv = (self.node.metadata or {}).get("inventory") or {}
        self.assertEqual(inv.get("disk_total_bytes"), 1_500_000_000_000)
        self.assertEqual(inv.get("disk_used_bytes"), 600_000_000_000)
        self.assertEqual(inv.get("disk_free_bytes"), 900_000_000_000)
        self.assertEqual(inv.get("disk_count"), 2)


class NodeMonitorReadApiCommunityTests(TestCase):
    """HTTP-level check: community process has no node-monitor read routes.

    URL-pattern gating (both on/off) is covered in ``test_monitor_url_gating``
    without requiring EE. This class only runs when the process itself is a
    community socket so Django's live URLconf matches that edition.
    """

    def setUp(self):
        if extensions_enabled():
            self.skipTest("live URLconf has extension routes; see test_monitor_url_gating")
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="node-monitor-community@test.local",
            email="node-monitor-community@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="node-monitor-community", name="Community Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_X_ORG_KEY=self.org.key)

    def test_list_nodes_unavailable_without_extension(self):
        resp = self.client.get("/api/v1/monitors/nodes/", {"role": "agent"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_node_detail_unavailable_without_extension(self):
        resp = self.client.get("/api/v1/monitors/nodes/1/", {"hours": "1"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
