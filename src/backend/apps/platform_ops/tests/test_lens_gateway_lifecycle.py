"""Platform-scoped Data Gateway lifecycle API tests."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.iam.models import Organization
from apps.lens_bridge.services import platform_lens
from apps.node.models import Node
from apps.node.models.base import NodeRole


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsLensGatewayLifecycleTests(TestCase):
    """Ensure Admin Engine lifecycle calls stay in the hidden platform org."""

    def setUp(self) -> None:
        lifecycle_routable_patcher = patch(
            "apps.node.services.internal.node_lifecycle.agent_ws_routable",
            return_value=False,
        )
        watch_routable_patcher = patch(
            "apps.node.api.serializers.lifecycle_watch.agent_ws_routable",
            return_value=False,
        )
        lifecycle_routable_patcher.start()
        watch_routable_patcher.start()
        self.addCleanup(lifecycle_routable_patcher.stop)
        self.addCleanup(watch_routable_patcher.stop)
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="platform-lifecycle@test.local",
            email="platform-lifecycle@test.local",
            password="test-pass",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.platform_org = platform_lens.get_or_create_platform_org()
        self.gateway = Node.objects.create(
            organization=self.platform_org,
            name="platform-gateway",
            role=NodeRole.GATEWAY,
            status=Node.Status.OFFLINE,
        )

    def _post(self, path: str, body: dict) -> Response:
        return self.client.post(
            path,
            body,
            format="json",
            HTTP_X_HFL_SITE_ROLE="ops",
        )

    def test_preview_uses_hidden_platform_organization(self) -> None:
        tenant_org = Organization.objects.create(key="tenant", name="Tenant")
        tenant_gateway = Node.objects.create(
            organization=tenant_org,
            name="tenant-gateway",
            role=NodeRole.GATEWAY,
        )
        platform_agent = Node.objects.create(
            organization=self.platform_org,
            name="platform-agent",
            role=NodeRole.AGENT,
        )

        response = self._post(
            "/api/v1/platform-ops/lens/gateways/operations/preview",
            {
                "kind": "remove",
                "node_ids": [
                    self.gateway.id,
                    tenant_gateway.id,
                    platform_agent.id,
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["node_id"] for row in response.data["eligible"]],
            [self.gateway.id],
        )
        self.assertEqual(
            response.data["missing_node_ids"],
            [tenant_gateway.id, platform_agent.id],
        )

    @patch(
        "apps.platform_ops.api.views.lens._start_platform_gateway_operation",
        return_value={
            "operation_id": "op-1",
            "task_id": "task-1",
            "node_id": 1,
            "kind": "remove",
            "state": "removing",
        },
    )
    def test_batch_dispatches_platform_gateway(self, mock_start) -> None:
        response = self._post(
            "/api/v1/platform-ops/lens/gateways/operations/batch",
            {"kind": "remove", "node_ids": [self.gateway.id]},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(response.data["started"]), 1)
        mock_start.assert_called_once()
        self.assertEqual(mock_start.call_args.kwargs["gateway"], self.gateway)
        self.assertEqual(mock_start.call_args.kwargs["kind"], "remove")

    def test_lifecycle_watch_excludes_tenant_gateways(self) -> None:
        tenant_org = Organization.objects.create(key="other", name="Other")
        tenant_gateway = Node.objects.create(
            organization=tenant_org,
            name="other-gateway",
            role=NodeRole.GATEWAY,
        )

        response = self._post(
            "/api/v1/platform-ops/lens/gateways/lifecycle-watch",
            {"node_ids": [self.gateway.id, tenant_gateway.id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["nodes"]],
            [self.gateway.id],
        )
