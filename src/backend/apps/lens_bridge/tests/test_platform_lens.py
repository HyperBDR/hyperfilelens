"""Platform Gateway selection tests."""

from __future__ import annotations

from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.lens_bridge.models import LensGatewayLink
from apps.lens_bridge.services import platform_lens
from apps.node.models import Node
from apps.node.models.base import NodeRole


class PlatformGatewaySelectionTests(TestCase):
    def test_explicit_platform_default_is_selected_before_older_gateway(self):
        org = platform_lens.get_or_create_platform_org()
        older_gateway = Node.objects.create(
            organization=org,
            name="older-gateway",
            role=NodeRole.GATEWAY,
        )
        selected_gateway = Node.objects.create(
            organization=org,
            name="selected-gateway",
            role=NodeRole.GATEWAY,
        )
        LensGatewayLink.objects.create(
            organization=org,
            gateway=older_gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            origin=LensGatewayLink.Origin.PLATFORM,
            sl_lensnode_uuid="9f16dace-78ae-4979-9e88-a63d6c641f8e",
            sidecar_status=LensGatewayLink.SidecarStatus.ONLINE,
        )
        selected = LensGatewayLink.objects.create(
            organization=org,
            gateway=selected_gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            origin=LensGatewayLink.Origin.PLATFORM,
            sl_lensnode_uuid="e440d5a4-2dc0-4ff9-b268-5afee3211d30",
            sidecar_status=LensGatewayLink.SidecarStatus.ONLINE,
            is_platform_default=True,
        )

        with mock.patch(
            "apps.lens_bridge.services.platform_lens.gateway_runtime_state",
            return_value={"copilot_eligible": True},
        ):
            resolved = platform_lens.resolve_platform_default_gateway_link()

        self.assertEqual(resolved, selected)

    def test_database_rejects_multiple_live_platform_defaults(self):
        org = platform_lens.get_or_create_platform_org()
        first_gateway = Node.objects.create(
            organization=org,
            name="first-default",
            role=NodeRole.GATEWAY,
        )
        second_gateway = Node.objects.create(
            organization=org,
            name="second-default",
            role=NodeRole.GATEWAY,
        )
        LensGatewayLink.objects.create(
            organization=org,
            gateway=first_gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            owner_user=None,
            is_platform_default=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            LensGatewayLink.objects.create(
                organization=org,
                gateway=second_gateway,
                scope=LensGatewayLink.GatewayScope.PLATFORM,
                owner_user=None,
                is_platform_default=True,
            )

    @mock.patch(
        "apps.lens_bridge.services.platform_lens.require_hfl_usable_gateway"
    )
    def test_setting_a_new_default_clears_the_previous_default(self, _ready):
        org = platform_lens.get_or_create_platform_org()
        first_gateway = Node.objects.create(
            organization=org,
            name="previous-default",
            role=NodeRole.GATEWAY,
        )
        second_gateway = Node.objects.create(
            organization=org,
            name="replacement-default",
            role=NodeRole.GATEWAY,
        )
        previous = LensGatewayLink.objects.create(
            organization=org,
            gateway=first_gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            owner_user=None,
            is_platform_default=True,
        )
        replacement = LensGatewayLink.objects.create(
            organization=org,
            gateway=second_gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            owner_user=None,
        )

        platform_lens.set_platform_default_gateway(gateway_link_id=replacement.id)

        previous.refresh_from_db()
        replacement.refresh_from_db()
        self.assertFalse(previous.is_platform_default)
        self.assertTrue(replacement.is_platform_default)
