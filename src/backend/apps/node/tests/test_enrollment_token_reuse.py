"""Enrollment token reuse and expiry."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.iam.models import Organization
from apps.node.api.serializers import NodeTokenCreateSerializer
from apps.node.api.views.node import NodeViewSet
from apps.node.models import Node, NodeToken
from apps.node.models.base import NodeRole


class EnrollmentTokenReuseTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="reuse-org", name="Reuse Org")
        self.token_row = NodeToken.objects.create(
            organization=self.org,
            role=NodeRole.AGENT,
            token="reuse-token-abc",
            is_active=True,
        )
        self.factory = APIRequestFactory()

    def _heartbeat(self, *, name: str, token: str | None = None):
        request = self.factory.post(
            "/api/v1/node/nodes/heartbeat/",
            {
                "role": "agent",
                "name": name,
                "version": "1.0.0",
                "os_name": "linux",
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
            HTTP_X_NODE_TOKEN=token or self.token_row.token,
        )
        return NodeViewSet.as_view({"post": "heartbeat"})(request)

    def test_same_token_registers_multiple_nodes(self):
        first = self._heartbeat(name="host-a")
        self.assertEqual(first.status_code, 200)
        second = self._heartbeat(name="host-b")
        self.assertEqual(second.status_code, 200)

        self.token_row.refresh_from_db()
        self.assertTrue(self.token_row.is_active)
        self.assertIsNotNone(self.token_row.used_at)
        self.assertEqual(Node.objects.filter(organization=self.org).count(), 2)

    @mock.patch("apps.node.api.views.node.sync_agent_source_host", side_effect=RuntimeError("sync failed"))
    def test_source_host_sync_failure_does_not_break_registration(self, _mock_sync):
        response = self._heartbeat(name="host-sync-fails")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Node.objects.filter(organization=self.org).count(), 1)

    def test_expired_token_rejects_new_registration(self):
        self.token_row.expires_at = timezone.now() - timedelta(minutes=1)
        self.token_row.save(update_fields=["expires_at"])

        response = self._heartbeat(name="host-expired")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Node.objects.filter(organization=self.org).count(), 0)

    def test_create_serializer_sets_default_expiry(self):
        ser = NodeTokenCreateSerializer(data={"role": NodeRole.AGENT})
        self.assertTrue(ser.is_valid(), ser.errors)
        row = ser.save(organization=self.org)
        self.assertIsNotNone(row.expires_at)
        self.assertGreater(row.expires_at, timezone.now())

    def test_create_serializer_honors_explicit_null_expiry(self):
        ser = NodeTokenCreateSerializer(data={"role": NodeRole.AGENT, "expires_at": None})
        self.assertTrue(ser.is_valid(), ser.errors)
        row = ser.save(organization=self.org)
        self.assertIsNone(row.expires_at)
