"""Installer-managed local platform Gateway tests."""

from __future__ import annotations

import io
import json
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.lens_bridge.models import LensGatewayLink
from apps.lens_bridge.services import platform_lens, provisioning
from apps.node.api.views.node import NodeViewSet
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.local_platform_gateway import (
    LOCAL_PLATFORM_GATEWAY_INSTALL_KEY,
    LOCAL_PLATFORM_GATEWAY_METADATA,
    LOCAL_PLATFORM_GATEWAY_TOKEN_NOTE,
    ensure_local_platform_gateway_token,
    platform_gateway_api_base,
    registration_metadata,
)


class LocalPlatformGatewayConfigTests(SimpleTestCase):
    @override_settings(FRONTEND_URL="https://console.example.com:11443/")
    def test_platform_gateway_api_base_returns_canonical_origin(self):
        self.assertEqual(
            platform_gateway_api_base(),
            "https://console.example.com:11443",
        )

    @override_settings(FRONTEND_URL="https://console.example.com/tenant")
    def test_platform_gateway_api_base_rejects_paths(self):
        with self.assertRaisesMessage(ValueError, "FRONTEND_URL"):
            platform_gateway_api_base()

    @override_settings(
        FRONTEND_URL="http://console.example.com:11443",
        HFL_INSECURE_TLS=False,
    )
    def test_platform_gateway_api_base_requires_https_in_strict_mode(self):
        with self.assertRaisesMessage(ValueError, "must use HTTPS"):
            platform_gateway_api_base()

    def test_registration_metadata_requires_trusted_installer_state(self):
        untrusted = registration_metadata(LOCAL_PLATFORM_GATEWAY_METADATA)
        self.assertNotIn("install_key", untrusted)

        managed = registration_metadata(
            {"hostname": "gateway-host"},
            token_note=LOCAL_PLATFORM_GATEWAY_TOKEN_NOTE,
        )
        self.assertEqual(managed["install_key"], LOCAL_PLATFORM_GATEWAY_INSTALL_KEY)
        self.assertEqual(managed["hostname"], "gateway-host")


@override_settings(FRONTEND_URL="https://console.example.com:11443")
class LocalPlatformGatewayEnrollmentTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_token_is_reused(self):
        first = ensure_local_platform_gateway_token()
        second = ensure_local_platform_gateway_token()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.organization.key, platform_lens.PLATFORM_ORG_KEY)
        self.assertEqual(first.role, NodeRole.GATEWAY)
        self.assertEqual(first.gateway_scope, LensGatewayLink.GatewayScope.PLATFORM)

    def test_management_command_emits_machine_readable_enrollment(self):
        org = platform_lens.get_or_create_platform_org()
        managed = Node.objects.create(
            organization=org,
            name="managed-gateway",
            role=NodeRole.GATEWAY,
            metadata=dict(LOCAL_PLATFORM_GATEWAY_METADATA),
        )
        Node.objects.create(
            organization=org,
            name="partial-metadata-gateway",
            role=NodeRole.GATEWAY,
            metadata={"install_key": LOCAL_PLATFORM_GATEWAY_INSTALL_KEY},
        )
        stdout = io.StringIO()

        call_command("ensure_local_platform_gateway_enrollment", stdout=stdout)

        line = stdout.getvalue().strip()
        prefix = "HFL_LOCAL_PLATFORM_GATEWAY_ENROLLMENT="
        self.assertTrue(line.startswith(prefix))
        payload = json.loads(line.removeprefix(prefix))
        self.assertEqual(payload["org_key"], platform_lens.PLATFORM_ORG_KEY)
        self.assertEqual(payload["api_base"], "https://console.example.com:11443")
        self.assertEqual(
            payload["wss_url"],
            "wss://console.example.com:11443/ws/node/agent/",
        )
        self.assertTrue(payload["token"])
        self.assertEqual(payload["managed_node_ids"], [managed.id])

    @mock.patch(
        "apps.lens_bridge.services.provisioning.provision_gateway_lens_on_register",
        return_value=None,
    )
    def test_installer_metadata_survives_followup_heartbeat(self, _mock_provision):
        token = ensure_local_platform_gateway_token()
        first_request = self.factory.post(
            "/api/v1/node/nodes/heartbeat/",
            {
                "role": NodeRole.GATEWAY,
                "name": "gateway-host",
                "version": "1.0.0",
                "os_name": "linux amd64",
                "metadata": {"hostname": "gateway-host"},
            },
            format="json",
            HTTP_X_ORG_KEY=token.organization.key,
            HTTP_X_NODE_TOKEN=token.token,
        )
        first_response = NodeViewSet.as_view({"post": "heartbeat"})(first_request)
        self.assertEqual(first_response.status_code, 200)
        node = Node.objects.get(pk=first_response.data["node_id"])
        self.assertEqual(node.metadata["install_key"], LOCAL_PLATFORM_GATEWAY_INSTALL_KEY)

        second_request = self.factory.post(
            "/api/v1/node/nodes/heartbeat/",
            {
                "node_id": node.id,
                "role": NodeRole.GATEWAY,
                "name": "gateway-host",
                "version": "1.0.0",
                "os_name": "linux amd64",
                "metadata": {"hostname": "gateway-host", "agent_version": "1.0.0"},
            },
            format="json",
            HTTP_X_ORG_KEY=token.organization.key,
            HTTP_X_NODE_TOKEN=token.token,
        )
        second_response = NodeViewSet.as_view({"post": "heartbeat"})(second_request)
        self.assertEqual(second_response.status_code, 200)
        node.refresh_from_db()
        self.assertEqual(node.metadata["install_key"], LOCAL_PLATFORM_GATEWAY_INSTALL_KEY)
        self.assertEqual(node.metadata["agent_version"], "1.0.0")

    @mock.patch(
        "apps.lens_bridge.services.provisioning.sl_client.request_json",
        return_value={
            "uuid": "aa8cd5e8-364e-4cc5-816e-3c54fe72119f",
            "token": "lensnode-token",
        },
    )
    def test_first_installer_gateway_becomes_platform_default(self, _mock_sl):
        org = platform_lens.get_or_create_platform_org()
        gateway = Node.objects.create(
            organization=org,
            name="gateway-host",
            role=NodeRole.GATEWAY,
            metadata=dict(LOCAL_PLATFORM_GATEWAY_METADATA),
        )

        link = provisioning.ensure_lensnode_for_gateway(
            org=org,
            gateway=gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
        )

        self.assertTrue(link.is_platform_default)

    @mock.patch(
        "apps.lens_bridge.services.provisioning.sl_client.request_json",
        return_value={
            "uuid": "f077f894-38c9-4576-8de4-808cb320b67c",
            "token": "lensnode-token",
        },
    )
    def test_installer_gateway_does_not_override_existing_platform_default(self, _mock_sl):
        org = platform_lens.get_or_create_platform_org()
        current_gateway = Node.objects.create(
            organization=org,
            name="current-default",
            role=NodeRole.GATEWAY,
        )
        current_default = LensGatewayLink.objects.create(
            organization=org,
            gateway=current_gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            origin=LensGatewayLink.Origin.PLATFORM,
            sl_lensnode_uuid="b1e3bfc3-ac2c-4721-803f-121849e92728",
            is_platform_default=True,
        )
        local_gateway = Node.objects.create(
            organization=org,
            name="gateway-host",
            role=NodeRole.GATEWAY,
            metadata=dict(LOCAL_PLATFORM_GATEWAY_METADATA),
        )

        local_link = provisioning.ensure_lensnode_for_gateway(
            org=org,
            gateway=local_gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
        )

        current_default.refresh_from_db()
        self.assertTrue(current_default.is_platform_default)
        self.assertFalse(local_link.is_platform_default)
