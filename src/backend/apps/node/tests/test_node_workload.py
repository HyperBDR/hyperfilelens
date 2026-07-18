"""Tests for node workload guards."""

from django.test import TestCase

from apps.iam.models import Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.node_lifecycle import enrich_node_row
from apps.node.services.internal.node_workload import node_workload_payload


class NodeWorkloadTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="workload-org", name="Workload Org")
        self.proxy = Node.objects.create(
            organization=self.org,
            name="proxy-1",
            role=NodeRole.PROXY,
            status=Node.Status.ONLINE,
            version="1.0.0",
        )

    def test_proxy_workload_payload_does_not_query_missing_fields(self):
        payload = node_workload_payload(node=self.proxy)
        self.assertEqual(payload, {"blocked": False, "reasons": []})

    def test_proxy_enrich_row_succeeds(self):
        row = enrich_node_row(org=self.org, node=self.proxy)
        self.assertIn("workload", row)
        self.assertIn("lifecycle", row)
