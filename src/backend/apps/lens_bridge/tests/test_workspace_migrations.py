import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.iam.models import Organization
from apps.lens_bridge.models import (
    LensGatewayLink,
    LensKnowledgeSource,
    LensWorkspaceBinding,
)
from apps.node.models import Node
from apps.node.services.internal.task import create_agent_task


class WorkspaceInvariantTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            key="workspace-invariant-org",
            name="Workspace invariant",
        )
        self.user = get_user_model().objects.create_user(
            username="workspace-invariant@example.test",
            email="workspace-invariant@example.test",
        )
        self.gateway = Node.objects.create(
            organization=self.organization,
            name="private-gateway",
            role=Node.Role.GATEWAY,
        )
        self.link = LensGatewayLink.objects.create(
            organization=self.organization,
            gateway=self.gateway,
            owner_user=self.user,
            scope=LensGatewayLink.GatewayScope.USER,
            workspace_root="/workspace/tenant/data",
        )

    def _knowledge_source(self, *, name: str = "Managed KS") -> LensKnowledgeSource:
        return LensKnowledgeSource.objects.create(
            organization=self.organization,
            name=name,
            gateway=self.gateway,
            gateway_link=self.link,
            backup_source_snapshot_id=7,
            backup_snapshot_directory_id=8,
            source_path="/data",
            created_by=self.user,
        )

    def test_resolved_path_rejects_parent_traversal(self):
        binding = LensWorkspaceBinding(
            organization=self.organization,
            knowledge_source=self._knowledge_source(),
            gateway_link=self.link,
            execution_organization_id=self.organization.id,
            execution_node_id=self.gateway.id,
            workspace_kind=LensWorkspaceBinding.WorkspaceKind.MANAGED_RESTORE,
            workspace_root="/workspace/tenant/data",
            relative_path="../another-tenant",
        )

        with self.assertRaises(ValueError):
            binding.resolved_path()

    def test_database_rejects_managed_workspace_without_relative_path(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LensWorkspaceBinding.objects.create(
                organization=self.organization,
                knowledge_source=self._knowledge_source(),
                gateway_link=self.link,
                execution_organization_id=self.organization.id,
                execution_node_id=self.gateway.id,
                workspace_kind=LensWorkspaceBinding.WorkspaceKind.MANAGED_RESTORE,
                workspace_root="/workspace/tenant/data",
                relative_path="",
                state=LensWorkspaceBinding.State.PREPARING,
                identity_status=LensWorkspaceBinding.IdentityStatus.PENDING,
            )

    def test_database_rejects_private_gateway_without_owner(self):
        another_gateway = Node.objects.create(
            organization=self.organization,
            name="ownerless-gateway",
            role=Node.Role.GATEWAY,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            LensGatewayLink.objects.create(
                organization=self.organization,
                gateway=another_gateway,
                scope=LensGatewayLink.GatewayScope.USER,
            )

    def test_workspace_identity_payload_persists_as_json(self):
        from apps.lens_bridge.services.gateway_execution import (
            workspace_identity_payload,
        )

        binding = LensWorkspaceBinding.objects.create(
            organization=self.organization,
            knowledge_source=self._knowledge_source(name="JSON-safe KS"),
            gateway_link=self.link,
            execution_organization_id=self.organization.id,
            execution_node_id=self.gateway.id,
            workspace_kind=LensWorkspaceBinding.WorkspaceKind.MANAGED_RESTORE,
            workspace_root="/workspace/tenant/data",
            relative_path="tenants/1/knowledge-sources/json-safe",
            state=LensWorkspaceBinding.State.PREPARING,
            identity_status=LensWorkspaceBinding.IdentityStatus.PENDING,
        )
        payload = {
            "path": binding.resolved_path(),
            **workspace_identity_payload(binding),
        }

        json.dumps(payload)
        task = create_agent_task(
            org=self.organization,
            node=self.gateway,
            kind="lens.ks.prepare",
            payload=payload,
        )

        self.assertEqual(task.payload["workspace_uid"], str(binding.workspace_uid))
        self.assertEqual(task.requesting_organization_id, self.organization.id)
