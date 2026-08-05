from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.node import conf as node_conf
from apps.iam.models import Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.task_offline_reconcile import (
    is_node_offline_stale,
    offline_stale_threshold_seconds,
    product_task_blocks_cleanup,
    task_execution_state,
)
from apps.task.models import Task


class OfflineStaleThresholdTests(SimpleTestCase):
    def test_offline_stale_threshold_includes_reconnect_and_fail_grace(self):
        expected = node_conf.NODE_RECONNECT_GRACE_SECONDS + node_conf.OFFLINE_TASK_FAIL_SECONDS
        self.assertEqual(offline_stale_threshold_seconds(), expected)


class TaskExecutionStateTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="offline-org", name="Offline Org")
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-offline",
            role=NodeRole.AGENT,
            status=Node.Status.ACTIVE, availability=Node.Availability.ONLINE,
            last_seen_at=timezone.now() - timedelta(seconds=300),
        )
        self.task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Backup",
            status=Task.Status.RUNNING,
            trigger_type=Task.TriggerType.MANUAL,
            request_payload={
                "source_type": "agent",
                "source_ref_id": self.node.id,
            },
        )

    @patch(
        "apps.node.services.internal.task_offline_reconcile.redis_store.offline_task_finalization_ready",
        return_value=True,
    )
    def test_offline_stale_when_last_seen_beyond_threshold(self, _mock_ready):
        self.assertTrue(is_node_offline_stale(self.node))

    def test_reconnecting_state_within_grace(self):
        self.node.availability = Node.Availability.ONLINE
        self.node.last_seen_at = timezone.now() - timedelta(seconds=30)
        self.node.save(update_fields=["availability", "last_seen_at", "updated_at"])
        self.assertEqual(task_execution_state(node=self.node, task=self.task), "reconnecting")
        self.assertTrue(product_task_blocks_cleanup(task=self.task))

    @patch(
        "apps.node.services.internal.task_offline_reconcile.redis_store.offline_task_finalization_ready",
        return_value=True,
    )
    def test_offline_pending_blocks_cleanup(self, _mock_ready):
        self.node.availability = Node.Availability.OFFLINE
        self.node.last_seen_at = timezone.now() - timedelta(
            seconds=node_conf.NODE_RECONNECT_GRACE_SECONDS + 10
        )
        self.node.save(update_fields=["availability", "last_seen_at", "updated_at"])
        self.assertEqual(task_execution_state(node=self.node, task=self.task), "offline_pending")
        self.assertTrue(product_task_blocks_cleanup(task=self.task))

    @patch(
        "apps.node.services.internal.task_offline_reconcile.redis_store.offline_task_finalization_ready",
        return_value=True,
    )
    def test_offline_stale_does_not_block_cleanup(self, _mock_ready):
        self.node.last_seen_at = timezone.now() - timedelta(
            seconds=offline_stale_threshold_seconds() + 5
        )
        self.node.save(update_fields=["last_seen_at", "updated_at"])
        self.assertEqual(task_execution_state(node=self.node, task=self.task), "offline_stale")
        self.assertFalse(product_task_blocks_cleanup(task=self.task))

    @patch(
        "apps.node.services.internal.task_offline_reconcile.redis_store.offline_task_finalization_ready",
        return_value=False,
    )
    def test_recovery_hold_keeps_stale_node_in_offline_pending(self, _mock_ready):
        self.assertFalse(is_node_offline_stale(self.node))
        self.assertEqual(task_execution_state(node=self.node, task=self.task), "offline_pending")
        self.assertTrue(product_task_blocks_cleanup(task=self.task))
