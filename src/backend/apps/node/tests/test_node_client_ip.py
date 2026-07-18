from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory

from apps.iam.models import Organization
from apps.node.api.views.node import NodeViewSet
from apps.node.models import Node, NodeToken
from apps.node.models.base import NodeRole
from common.http.client_ip import client_ip_from_meta, client_ip_from_scope


class ClientIpHelperTests(SimpleTestCase):
    def test_prefers_x_forwarded_for(self):
        meta = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.10, 172.18.0.7",
            "REMOTE_ADDR": "172.18.0.7",
        }
        self.assertEqual(client_ip_from_meta(meta), "203.0.113.10")

    def test_falls_back_to_remote_addr(self):
        meta = {"REMOTE_ADDR": "10.0.0.8"}
        self.assertEqual(client_ip_from_meta(meta), "10.0.0.8")

    def test_scope_reads_forwarded_header(self):
        scope = {
            "headers": [
                (b"x-forwarded-for", b"192.168.10.15, 172.18.0.7"),
            ],
            "client": ("172.18.0.7", 12345),
        }
        self.assertEqual(client_ip_from_scope(scope), "192.168.10.15")


class NodeHeartbeatClientIpTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="node-ip-org", name="Node IP Org")
        self.token_row = NodeToken.objects.create(
            organization=self.org,
            role=NodeRole.AGENT,
            token="enroll-token-123",
            is_active=True,
        )
        self.factory = APIRequestFactory()

    def test_heartbeat_persists_forwarded_client_ip(self):
        request = self.factory.post(
            "/api/v1/node/nodes/heartbeat/",
            {
                "role": "agent",
                "name": "agent-host",
                "version": "1.0.0",
                "os_name": "linux",
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
            HTTP_X_NODE_TOKEN=self.token_row.token,
            HTTP_X_FORWARDED_FOR="192.168.10.15",
            REMOTE_ADDR="172.18.0.7",
        )
        response = NodeViewSet.as_view({"post": "heartbeat"})(request)
        self.assertEqual(response.status_code, 200)

        node = Node.objects.get(organization=self.org)
        self.assertEqual(str(node.ip_address), "192.168.10.15")

    def test_heartbeat_updates_existing_node_ip(self):
        node = Node.objects.create(
            organization=self.org,
            name="agent-existing",
            role=NodeRole.AGENT,
            ip_address="172.18.0.7",
        )
        request = self.factory.post(
            "/api/v1/node/nodes/heartbeat/",
            {
                "node_id": node.id,
                "role": "agent",
                "name": node.name,
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
            HTTP_X_NODE_TOKEN="ignored",
            HTTP_X_FORWARDED_FOR="192.168.7.51",
            REMOTE_ADDR="172.18.0.7",
        )
        response = NodeViewSet.as_view({"post": "heartbeat"})(request)
        self.assertEqual(response.status_code, 200)

        node.refresh_from_db()
        self.assertEqual(str(node.ip_address), "192.168.7.51")
