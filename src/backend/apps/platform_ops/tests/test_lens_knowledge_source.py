"""Platform Ops Knowledge Source lifecycle tests."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.lens_bridge.models import (
    LensGatewayLink,
    LensKnowledgeSource,
    LensWorkspaceBinding,
)
from apps.lens_bridge.services import platform_lens
from apps.node.models import Node


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsKnowledgeSourceTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="platform-ks@example.test",
            email="platform-ks@example.test",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        organization = platform_lens.get_or_create_platform_org()
        gateway = Node.objects.create(
            organization=organization,
            name="platform-gateway",
            role=Node.Role.GATEWAY,
        )
        gateway_link = LensGatewayLink.objects.create(
            organization=organization,
            gateway=gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            origin=LensGatewayLink.Origin.PLATFORM,
            workspace_root=f"/workspace/org-{organization.id}/data",
        )
        self.knowledge_source = LensKnowledgeSource.objects.create(
            organization=organization,
            name="Platform KS",
            gateway=gateway,
            gateway_link=gateway_link,
            source_path=f"/workspace/org-{organization.id}/data/documents",
            status=LensKnowledgeSource.Status.READY,
        )
        LensWorkspaceBinding.objects.create(
            organization=organization,
            knowledge_source=self.knowledge_source,
            gateway_link=gateway_link,
            execution_organization_id=organization.id,
            execution_node_id=gateway.id,
            workspace_kind=LensWorkspaceBinding.WorkspaceKind.GATEWAY_LOCAL,
            workspace_root=gateway_link.workspace_root,
            state=LensWorkspaceBinding.State.READY,
            identity_status=LensWorkspaceBinding.IdentityStatus.NOT_APPLICABLE,
        )

    @patch(
        "apps.lens_bridge.tasks.knowledge_source_teardown."
        "execute_knowledge_source_teardown_task.delay"
    )
    def test_delete_is_asynchronous(self, delay) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(
                "/api/v1/platform-ops/lens/knowledge-sources/"
                f"{self.knowledge_source.id}"
            )

        self.assertEqual(response.status_code, 202)
        self.knowledge_source.refresh_from_db()
        self.assertEqual(
            self.knowledge_source.lifecycle_status,
            LensKnowledgeSource.LifecycleStatus.DELETING,
        )
        delay.assert_called_once_with(
            knowledge_source_id=self.knowledge_source.id
        )
