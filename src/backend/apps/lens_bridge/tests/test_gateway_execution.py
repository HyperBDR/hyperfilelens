from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import LensGatewayLink, LensKnowledgeSource
from apps.lens_bridge.services import platform_lens
from apps.lens_bridge.services.gateway_execution import context_for_gateway_link
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.node_workload import get_node_remove_blockers


class GatewayExecutionContextTests(TestCase):
    def setUp(self):
        self.tenant = Organization.objects.create(key="tenant-exec", name="Tenant")
        self.user = get_user_model().objects.create_user(
            username="gateway-exec@example.test",
            email="gateway-exec@example.test",
        )

    @mock.patch("apps.lens_bridge.services.gateway_execution.gateway_readiness.require_copilot_gateway")
    def test_platform_gateway_keeps_tenant_data_and_uses_platform_execution(self, _ready):
        platform_org = platform_lens.get_or_create_platform_org()
        node = Node.objects.create(
            organization=platform_org,
            name="shared-platform-gateway",
            role=NodeRole.GATEWAY,
            status=Node.Status.ONLINE,
        )
        link = LensGatewayLink.objects.create(
            organization=platform_org,
            gateway=node,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            origin=LensGatewayLink.Origin.PLATFORM,
            workspace_root="/workspace/org-platform/data",
        )

        context = context_for_gateway_link(
            tenant_organization=self.tenant,
            gateway_link=link,
        )

        self.assertEqual(context.tenant_organization, self.tenant)
        self.assertEqual(context.execution_organization, platform_org)
        self.assertTrue(context.is_platform)

    @mock.patch("apps.lens_bridge.services.gateway_execution.gateway_readiness.require_copilot_gateway")
    def test_private_gateway_cannot_cross_tenant_boundary(self, _ready):
        other_org = Organization.objects.create(key="other-exec", name="Other")
        node = Node.objects.create(
            organization=other_org,
            name="other-private-gateway",
            role=NodeRole.GATEWAY,
            status=Node.Status.ONLINE,
        )
        link = LensGatewayLink.objects.create(
            organization=other_org,
            gateway=node,
            owner_user=self.user,
            scope=LensGatewayLink.GatewayScope.USER,
        )

        with self.assertRaises(ValidationError):
            context_for_gateway_link(
                tenant_organization=self.tenant,
                gateway_link=link,
            )

    @mock.patch("apps.lens_bridge.services.gateway_execution.gateway_readiness.require_copilot_gateway")
    def test_private_gateway_cannot_cross_user_boundary(self, _ready):
        node = Node.objects.create(
            organization=self.tenant,
            name="private-user-gateway",
            role=NodeRole.GATEWAY,
            status=Node.Status.ONLINE,
        )
        link = LensGatewayLink.objects.create(
            organization=self.tenant,
            gateway=node,
            owner_user=self.user,
            scope=LensGatewayLink.GatewayScope.USER,
        )
        another_user = get_user_model().objects.create_user(
            username="another-gateway-user@example.test",
            email="another-gateway-user@example.test",
        )

        with self.assertRaises(ValidationError):
            context_for_gateway_link(
                tenant_organization=self.tenant,
                gateway_link=link,
                expected_owner_user_id=another_user.id,
            )

    def test_platform_gateway_removal_sees_tenant_knowledge_sources(self):
        platform_org = platform_lens.get_or_create_platform_org()
        node = Node.objects.create(
            organization=platform_org,
            name="platform-gateway-with-tenant-ks",
            role=NodeRole.GATEWAY,
        )
        link = LensGatewayLink.objects.create(
            organization=platform_org,
            gateway=node,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            origin=LensGatewayLink.Origin.PLATFORM,
        )
        LensKnowledgeSource.objects.create(
            organization=self.tenant,
            name="Tenant workspace",
            gateway=node,
            gateway_link=link,
            source_path="/backup/data",
        )

        blockers = get_node_remove_blockers(node=node)

        self.assertIn("knowledge_source_bound", {blocker.code for blocker in blockers})
