"""complete_task must not downgrade a terminal success on stale agent flush."""

from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from apps.iam.models import Organization
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.node.services.internal.task import complete_task


class CompleteTaskIdempotencyTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="complete-task-org", name="Complete Task Org")
        self.node = Node.objects.create(
            organization=self.org,
            name="complete-task-node",
            role=NodeRole.AGENT,
            status=Node.Status.ONLINE,
        )
        self.task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.SUCCESS,
            result={"mode": "local_detached"},
            watchdog_deadline_at=timezone.now(),
        )

    def test_stale_failed_result_does_not_overwrite_success(self):
        updated = complete_task(
            task_id=self.task.id,
            node_id=self.node.id,
            status="failed",
            error="agent restarted before task completed",
        )

        self.assertEqual(updated.status, NodeTask.Status.SUCCESS)
        self.assertEqual(updated.result, {"mode": "local_detached"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, NodeTask.Status.SUCCESS)
        self.assertEqual(self.task.last_error, "")

    def test_running_result_keeps_task_active_and_merges_result(self):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.PENDING,
            watchdog_deadline_at=timezone.now(),
        )
        updated = complete_task(
            task_id=task.id,
            node_id=self.node.id,
            status="running",
            result={
                "mode": "local_detached",
                "target_version": "1.2.0",
            },
        )
        self.assertEqual(updated.status, NodeTask.Status.RUNNING)
        self.assertEqual(updated.result.get("mode"), "local_detached")
        self.assertEqual(updated.result.get("target_version"), "1.2.0")

    def test_late_success_upgrades_failed_task_and_clears_error(self):
        self.task.status = NodeTask.Status.FAILED
        self.task.last_error = "Agent went offline during task execution."
        self.task.result = {"last_progress": {"phase": "repository_ready"}}
        self.task.save(update_fields=["status", "last_error", "result", "updated_at"])

        updated = complete_task(
            task_id=self.task.id,
            node_id=self.node.id,
            status="success",
            result={"kopia_snapshot_id": "late-kopia-id"},
        )

        self.assertEqual(updated.status, NodeTask.Status.SUCCESS)
        self.assertEqual(updated.last_error, "")
        self.assertEqual(updated.result["kopia_snapshot_id"], "late-kopia-id")

    def test_late_success_does_not_revive_cancelled_task(self):
        self.task.status = NodeTask.Status.CANCELED
        self.task.last_error = "canceled by user"
        self.task.save(update_fields=["status", "last_error", "updated_at"])

        updated = complete_task(
            task_id=self.task.id,
            node_id=self.node.id,
            status="success",
            result={"kopia_snapshot_id": "must-not-apply"},
        )

        self.assertEqual(updated.status, NodeTask.Status.CANCELED)
        self.assertEqual(updated.last_error, "canceled by user")
        self.assertNotIn("kopia_snapshot_id", updated.result)
