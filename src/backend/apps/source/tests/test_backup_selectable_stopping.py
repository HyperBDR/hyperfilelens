from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.iam.models import Organization
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.source.services.internal.backup_selectable import _product_task_is_stopping
from apps.task.models import Task


class ProductTaskStoppingTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="runtime-stopping", name="Runtime Stopping")
        self.node = Node.objects.create(
            organization=self.org,
            name="runtime-stopping-agent",
            role=NodeRole.AGENT,
        )
        self.task = Task.objects.create(
            organization_id=self.org.id,
            task_type=Task.Type.BACKUP,
            display_name="Backup",
            status=Task.Status.CANCELLED,
        )

    def create_node_task(self, *, age_seconds: int, cancel_requested: bool = True):
        return NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="backup.run",
            correlation_type="protection.backup",
            correlation_id=str(self.task.task_uuid),
            status=NodeTask.Status.RUNNING,
            cancel_requested_at=(
                timezone.now() - timezone.timedelta(seconds=age_seconds)
                if cancel_requested
                else None
            ),
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=2),
        )

    def test_stopping_only_during_cancel_grace(self):
        self.create_node_task(age_seconds=299)
        with patch("apps.node.conf.TASK_CANCEL_GRACE_SECONDS", 300):
            self.assertTrue(
                _product_task_is_stopping(organization_id=self.org.id, task=self.task)
            )

    def test_stopped_at_or_after_cancel_grace(self):
        self.create_node_task(age_seconds=301)
        with patch("apps.node.conf.TASK_CANCEL_GRACE_SECONDS", 300):
            self.assertFalse(
                _product_task_is_stopping(organization_id=self.org.id, task=self.task)
            )

    def test_active_task_without_cancel_request_is_not_stopping(self):
        self.create_node_task(age_seconds=0, cancel_requested=False)
        self.assertFalse(
            _product_task_is_stopping(organization_id=self.org.id, task=self.task)
        )
