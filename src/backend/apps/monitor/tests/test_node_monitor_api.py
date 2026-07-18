"""Node monitor API and ingest tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.monitor.models import ResourceMetric
from apps.monitor.services.internal.node_metrics import ingest_node_monitor_sample
from apps.node.models import Node
from apps.node.models.base import NodeRole


class NodeMonitorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="node-monitor@test.local",
            email="node-monitor@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="node-monitor-org", name="Node Monitor Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_X_ORG_KEY=self.org.key)
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-01",
            role=NodeRole.AGENT,
            status=Node.Status.ONLINE,
            metadata={"inventory": {"hostname": "agent-host", "os": "linux", "arch": "amd64"}},
        )

    def test_list_nodes_requires_org(self):
        bare = APIClient()
        bare.force_authenticate(user=self.user)
        resp = bare.get("/api/v1/monitors/nodes/", {"role": "agent"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["data"]["code"], "AUTH.FORBIDDEN")

    def test_list_nodes_by_role(self):
        resp = self.client.get("/api/v1/monitors/nodes/", {"role": "agent"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.data["data"] if "data" in resp.data else resp.data
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["id"], self.node.id)

    def test_node_monitor_detail_returns_series(self):
        sample = {
            "cpu": {"usage_percent": 12.5, "logical_cores": 4},
            "memory": {"total": 8_000_000_000, "available": 4_000_000_000, "percent": 50},
            "swap": {"percent": 0},
            "disks": [{"mountpoint": "/", "percent": 40, "used": 40, "total": 100}],
            "disk_io": [{"name": "sda", "read_bytes": 1000, "write_bytes": 2000}],
            "networks": [{"name": "eth0", "bytes_recv": 3000, "bytes_sent": 4000}],
            "load_average": [0.5, 0.4, 0.3],
            "boot_time": 1_700_000_000,
        }
        ingest_node_monitor_sample(node=self.node, sample=sample)

        resp = self.client.get(f"/api/v1/monitors/nodes/{self.node.id}/", {"hours": "1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.data["data"] if "data" in resp.data else resp.data
        self.assertIn("host", body)
        self.assertIn("series", body)
        self.assertGreaterEqual(len(body["series"]), 1)
        self.assertEqual(body["host"]["hostname"], "agent-host")

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
