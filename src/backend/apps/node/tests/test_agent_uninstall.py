"""Agent uninstall + server purge lifecycle."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.iam.models import Organization
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.node.services.internal.agent_uninstall import remove_agent_node
from apps.source.constants import ResourceType
from apps.source.models import SourceResource


class AgentUninstallTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="uninstall-org", name="Uninstall Org")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="uninstall@test.local",
            email="uninstall@test.local",
            password="test-pass",
        )
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-uninstall",
            role=NodeRole.AGENT,
            status=Node.Status.ACTIVE, availability=Node.Availability.OFFLINE,
            metadata={"capabilities": ["detached_uninstall_v2"]},
        )
        self.resource = SourceResource.objects.create(
            organization=self.org,
            name="host-1",
            resource_type=ResourceType.LOCAL,
            config={"root_path": "/"},
            bound_node=self.node,
        )

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_offline_skips_uninstall_still_purges(self, _routable):
        summary = remove_agent_node(
            org=self.org,
            node=self.node,
            user=self.user,
            force=True,
        )

        self.assertFalse(summary["uninstall_attempted"])
        self.node.refresh_from_db()
        self.resource.refresh_from_db()
        self.assertTrue(self.node.is_deleted)
        self.assertTrue(self.resource.is_deleted)
        self.assertEqual(summary["resources_removed"], 1)

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_gateway_offline_skips_uninstall_still_purges(self, _routable):
        gateway = Node.objects.create(
            organization=self.org,
            name="gateway-uninstall",
            role=NodeRole.GATEWAY,
            status=Node.Status.ACTIVE, availability=Node.Availability.OFFLINE,
        )
        summary = remove_agent_node(
            org=self.org,
            node=gateway,
            user=self.user,
            force=True,
        )
        self.assertFalse(summary["uninstall_attempted"])
        gateway.refresh_from_db()
        self.assertTrue(gateway.is_deleted)

    @patch("apps.node.services.internal.node_lifecycle.run_agent_task_async")
    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=True)
    def test_online_dispatches_uninstall_without_purging(
        self,
        _routable,
        mock_dispatch,
    ):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.uninstall",
            status=NodeTask.Status.PENDING,
            watchdog_deadline_at=timezone.now(),
        )
        mock_dispatch.return_value = type(
            "Handle",
            (),
            {"task_id": str(task.id), "task": task},
        )()
        summary = remove_agent_node(
            org=self.org,
            node=self.node,
            user=self.user,
            keep_data=True,
        )

        self.assertTrue(summary["uninstall_attempted"])
        mock_dispatch.assert_called_once()
        self.node.refresh_from_db()
        self.assertFalse(self.node.is_deleted)
        self.assertFalse(summary["server_records_purged"])
        self.assertEqual(summary["uninstall_task_status"], "running")
        self.assertEqual(
            mock_dispatch.call_args.kwargs["correlation_type"],
            "node.lifecycle",
        )
        self.assertEqual(
            mock_dispatch.call_args.kwargs["correlation_id"],
            f"remove:{self.node.id}",
        )
        self.assertEqual(
            mock_dispatch.call_args.kwargs["payload"],
            {"keep_data": True, "force_cleanup": False},
        )
