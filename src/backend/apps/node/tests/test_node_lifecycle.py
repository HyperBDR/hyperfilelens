"""Tests for node lifecycle operations."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.iam.models import Organization
from apps.node import conf as node_conf
from apps.node.exceptions import NodeLifecycleError
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.node.services.internal.node_lifecycle import (
    _version_matches_target,
    advance_node_lifecycle,
    compute_node_lifecycle,
    preview_batch_operations,
    start_node_remove,
    start_node_upgrade,
)
from apps.node.services.internal.task import complete_task


class NodeLifecycleTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="lifecycle-org", name="Lifecycle Org")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="lifecycle@test.local",
            email="lifecycle@test.local",
            password="test-pass",
        )
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-lifecycle",
            role=NodeRole.AGENT,
            status=Node.Status.ONLINE,
            version="1.0.0",
        )

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_offline_remove_purges_immediately(self, _routable):
        result = start_node_remove(org=self.org, node=self.node, user=self.user)
        self.assertEqual(result["state"], "completed")
        self.node.refresh_from_db()
        self.assertTrue(self.node.is_deleted)

    @patch("apps.node.services.internal.node_lifecycle.run_agent_task_async")
    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=True)
    def test_online_remove_dispatches_uninstall(self, _routable, mock_dispatch):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.uninstall",
            status=NodeTask.Status.RUNNING,
            watchdog_deadline_at=timezone.now(),
        )
        mock_dispatch.return_value = type(
            "Handle",
            (),
            {"task": task, "task_id": str(task.id)},
        )()

        result = start_node_remove(org=self.org, node=self.node, user=self.user)
        self.assertEqual(result["state"], "removing")
        mock_dispatch.assert_called_once()

    @patch("apps.node.services.internal.node_lifecycle.validate_agent_upgrade", return_value="1.2.0")
    @patch("apps.node.services.internal.node_lifecycle.run_agent_task_async")
    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=True)
    def test_start_upgrade_dispatches_task(self, _routable, mock_dispatch, _validate):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            result={"target_version": "1.2.0"},
            watchdog_deadline_at=timezone.now(),
        )
        mock_dispatch.return_value = type(
            "Handle",
            (),
            {"task": task, "task_id": str(task.id)},
        )()

        result = start_node_upgrade(org=self.org, node=self.node, user=self.user)
        self.assertEqual(result["state"], "upgrading")
        self.assertEqual(result["target_version"], "1.2.0")

    @patch("apps.node.services.internal.node_workload.get_node_workload_blockers")
    def test_upgrade_blocked_by_workload(self, mock_blockers):
        from apps.node.services.internal.node_workload import NodeWorkloadBlocker

        mock_blockers.return_value = [
            NodeWorkloadBlocker(
                code="backup_running",
                task_uuid="abc",
                task_type="backup",
                label="backup · nightly",
            )
        ]
        with self.assertRaises(NodeLifecycleError) as ctx:
            start_node_upgrade(org=self.org, node=self.node, user=self.user)
        self.assertEqual(ctx.exception.code, "node_workload_active")

    @patch("apps.node.services.internal.node_lifecycle.validate_agent_upgrade", return_value="1.2.0")
    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=True)
    def test_preview_batch_upgrade(self, _routable, _validate):
        preview = preview_batch_operations(
            org=self.org,
            node_ids=[self.node.id],
            kind="upgrade",
        )
        self.assertEqual(len(preview["eligible"]), 1)
        self.assertEqual(preview["eligible"][0]["target_version"], "1.2.0")

    def test_compute_upgrade_verifying_state(self):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.SUCCESS,
            result={"target_version": "1.2.0", "mode": "local_detached"},
            watchdog_deadline_at=timezone.now(),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        with patch("apps.node.services.internal.node_lifecycle.agent_session_registered", return_value=True):
            lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertIsNotNone(lifecycle)
        self.assertEqual(lifecycle["state"], "verifying")
        self.assertEqual(lifecycle["task_id"], str(task.id))

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_upgrade_success_clears_when_version_matches_despite_stale_ws(self, _routable):
        self.node.version = "1.2.0"
        self.node.save(update_fields=["version"])
        NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.SUCCESS,
            result={"target_version": "1.2.0", "mode": "local_detached"},
            watchdog_deadline_at=timezone.now(),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertIsNone(lifecycle)

    def test_main_build_version_matches_exact_commit(self):
        self.node.version = "main-123abcd"
        self.assertTrue(
            _version_matches_target(node=self.node, target_version="main-123abcd")
        )

    def test_main_build_version_rejects_different_commit(self):
        self.node.version = "main-7654321"
        self.assertFalse(
            _version_matches_target(node=self.node, target_version="main-123abcd")
        )

    def test_release_version_match_preserves_ordered_semver_behavior(self):
        self.node.version = "1.2.1"
        self.assertTrue(_version_matches_target(node=self.node, target_version="1.2.0"))

    @patch("apps.node.services.internal.node_lifecycle.agent_session_registered", return_value=False)
    def test_same_version_running_task_not_finalized_on_enrich(self, _session):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            payload={"target_version": "1.0.0"},
            result={"target_version": "1.0.0", "mode": "local_detached"},
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        advance_node_lifecycle(org=self.org, node=self.node, user=self.user)
        task.refresh_from_db()
        self.assertEqual(task.status, NodeTask.Status.RUNNING)
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertEqual(lifecycle["state"], "restarting")

    @patch("apps.node.services.internal.node_lifecycle.agent_session_registered", return_value=True)
    def test_same_version_detached_finalizes_after_reconnect(self, _session):
        stable_seconds = int(node_conf.UPGRADE_STABLE_SECONDS)
        verify_started = timezone.now() - timezone.timedelta(seconds=stable_seconds + 1)
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            payload={"target_version": "1.0.0"},
            result={
                "target_version": "1.0.0",
                "mode": "local_detached",
                "detached_at": timezone.now().isoformat(),
                "verify_started_at": verify_started.isoformat(),
            },
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        advance_node_lifecycle(org=self.org, node=self.node, user=self.user)
        task.refresh_from_db()
        self.assertEqual(task.status, NodeTask.Status.SUCCESS)

    @patch("apps.node.services.internal.node_lifecycle.agent_session_registered", return_value=True)
    def test_upgrade_verify_waits_for_stable_window(self, _session):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            payload={"target_version": "1.0.0"},
            result={
                "target_version": "1.0.0",
                "mode": "local_detached",
                "detached_at": timezone.now().isoformat(),
                "verify_started_at": timezone.now().isoformat(),
            },
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        advance_node_lifecycle(org=self.org, node=self.node, user=self.user)
        task.refresh_from_db()
        self.assertEqual(task.status, NodeTask.Status.RUNNING)
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertEqual(lifecycle["state"], "verifying")

    @patch("apps.node.services.internal.node_lifecycle.agent_session_registered", return_value=True)
    def test_upgrade_verify_starts_clock_on_first_stable_reconnect(self, _session):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            payload={"target_version": "1.0.0"},
            result={
                "target_version": "1.0.0",
                "mode": "local_detached",
                "detached_at": timezone.now().isoformat(),
            },
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        advance_node_lifecycle(org=self.org, node=self.node, user=self.user)
        task.refresh_from_db()
        self.assertEqual(task.status, NodeTask.Status.RUNNING)
        self.assertIn("verify_started_at", task.result or {})
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertEqual(lifecycle["state"], "verifying")

    @patch("apps.node.services.internal.node_lifecycle.agent_session_registered", return_value=False)
    def test_upgrade_verify_clears_clock_when_ws_drops(self, _session):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            payload={"target_version": "1.0.0"},
            result={
                "target_version": "1.0.0",
                "mode": "local_detached",
                "detached_at": timezone.now().isoformat(),
                "verify_started_at": timezone.now().isoformat(),
            },
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        advance_node_lifecycle(org=self.org, node=self.node, user=self.user)
        task.refresh_from_db()
        self.assertNotIn("verify_started_at", task.result or {})
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertEqual(lifecycle["state"], "restarting")

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_remove_finalizes_when_detached_and_ws_gone(self, _routable):
        detached_at = timezone.now() - timezone.timedelta(seconds=35)
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.uninstall",
            status=NodeTask.Status.RUNNING,
            result={
                "mode": "local_detached",
                "detached_at": detached_at.isoformat(),
            },
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"remove:{self.node.id}",
        )
        summary = advance_node_lifecycle(org=self.org, node=self.node, user=self.user)
        self.assertIsNotNone(summary)
        self.assertTrue(summary.get("purged"))
        task.refresh_from_db()
        self.assertEqual(task.status, NodeTask.Status.SUCCESS)
        self.node.refresh_from_db()
        self.assertTrue(self.node.is_deleted)

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_pending_remove_does_not_finalize_when_ws_gone(self, _routable):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.uninstall",
            status=NodeTask.Status.PENDING,
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"remove:{self.node.id}",
        )
        summary = advance_node_lifecycle(org=self.org, node=self.node, user=self.user)
        self.assertIsNone(summary)
        task.refresh_from_db()
        self.assertEqual(task.status, NodeTask.Status.PENDING)
        self.node.refresh_from_db()
        self.assertFalse(self.node.is_deleted)

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_upgrade_active_detached_task_shows_restarting_when_ws_gone(self, _routable):
        NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            result={
                "target_version": "1.2.0",
                "mode": "local_detached",
                "detached_at": timezone.now().isoformat(),
            },
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertEqual(lifecycle["state"], "restarting")

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_running_without_detached_marker_stays_upgrading(self, _routable):
        NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.RUNNING,
            result={"target_version": "1.2.0"},
            watchdog_deadline_at=timezone.now(),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertEqual(lifecycle["state"], "upgrading")

    @patch("apps.node.services.internal.node_lifecycle.agent_ws_routable", return_value=False)
    def test_remove_active_detached_shows_removing_before_finalize_window(self, _routable):
        NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.uninstall",
            status=NodeTask.Status.RUNNING,
            result={
                "mode": "local_detached",
                "detached_at": timezone.now().isoformat(),
            },
            watchdog_deadline_at=timezone.now() + timezone.timedelta(hours=1),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"remove:{self.node.id}",
        )
        lifecycle = compute_node_lifecycle(org=self.org, node=self.node)
        self.assertEqual(lifecycle["state"], "removing")

    def test_complete_task_running_extends_watchdog_for_detached(self):
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="agent.upgrade",
            status=NodeTask.Status.PENDING,
            watchdog_deadline_at=timezone.now(),
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=f"upgrade:{self.node.id}",
        )
        before = timezone.now()
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
        self.assertGreater(
            updated.watchdog_deadline_at,
            before + timezone.timedelta(seconds=node_conf.TASK_WATCHDOG_SECONDS),
        )
        self.assertIn("detached_at", updated.result or {})
