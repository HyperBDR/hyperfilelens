"""Synchronous Agent task waiting semantics."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from redis.exceptions import TimeoutError as RedisTimeoutError

from apps.iam.models import Organization
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.node.services.internal import redis_store
from apps.node.services.internal.agent_task import wait_for_agent_task
from apps.node.services.internal.task import deliver_agent_task, redeliver_pending_agent_task


class AgentTaskSyncWaitTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="agent-task-sync-org", name="Agent Task Sync Org")
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-task-sync",
            role=NodeRole.AGENT,
            status=Node.Status.ONLINE,
            last_seen_at=timezone.now(),
        )
        self.task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="explorer.list",
            status=NodeTask.Status.RUNNING,
            watchdog_deadline_at=timezone.now(),
        )

    @patch("apps.node.services.internal.agent_task.redis_store.bpop_task_stream")
    def test_wait_ignores_progress_until_terminal_result(self, mock_bpop):
        def pop_stream(*, task_id: str, timeout_seconds: int):
            if mock_bpop.call_count == 1:
                return {
                    "task_id": task_id,
                    "status": NodeTask.Status.RUNNING,
                    "progress": {"phase": "listing"},
                }
            NodeTask.objects.filter(pk=self.task.id).update(
                status=NodeTask.Status.SUCCESS,
                result={"entries": [{"name": "data", "path": "/data", "is_dir": True}]},
            )
            return {
                "task_id": task_id,
                "status": NodeTask.Status.SUCCESS,
                "result": {"entries": [{"name": "data", "path": "/data", "is_dir": True}]},
            }

        mock_bpop.side_effect = pop_stream

        outcome = wait_for_agent_task(task_id=self.task.id, timeout_seconds=5)

        self.assertFalse(outcome.timed_out)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.result["entries"][0]["path"], "/data")
        self.assertEqual(mock_bpop.call_count, 2)

    @patch("apps.node.services.internal.agent_task.redis_store.bpop_task_stream")
    def test_wait_rechecks_database_when_stream_terminal_message_is_missing(self, mock_bpop):
        def pop_stream(*, task_id: str, timeout_seconds: int):
            self.assertLessEqual(timeout_seconds, 5)
            NodeTask.objects.filter(pk=self.task.id).update(
                status=NodeTask.Status.SUCCESS,
                result={"entries": [{"name": "data", "path": "/data", "is_dir": True}]},
            )
            return None

        mock_bpop.side_effect = pop_stream

        outcome = wait_for_agent_task(task_id=self.task.id, timeout_seconds=3600)

        self.assertFalse(outcome.timed_out)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.result["entries"][0]["path"], "/data")
        self.assertEqual(mock_bpop.call_count, 1)

    @patch("apps.node.services.internal.agent_task.redis_store.bpop_task_stream")
    def test_wait_continues_after_empty_stream_when_task_is_still_running(self, mock_bpop):
        def pop_stream(*, task_id: str, timeout_seconds: int):
            self.assertLessEqual(timeout_seconds, 5)
            if mock_bpop.call_count == 1:
                return None
            NodeTask.objects.filter(pk=self.task.id).update(
                status=NodeTask.Status.SUCCESS,
                result={"entries": [{"name": "data", "path": "/data", "is_dir": True}]},
            )
            return None

        mock_bpop.side_effect = pop_stream

        outcome = wait_for_agent_task(task_id=self.task.id, timeout_seconds=6)

        self.assertFalse(outcome.timed_out)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.result["entries"][0]["path"], "/data")
        self.assertEqual(mock_bpop.call_count, 2)

    @patch("apps.node.services.internal.redis_store.get_redis")
    def test_task_stream_redis_socket_timeout_returns_no_message(self, mock_get_redis):
        class RedisClient:
            def blpop(self, key, timeout):
                raise RedisTimeoutError("Timeout reading from socket")

        mock_get_redis.return_value = RedisClient()

        message = redis_store.bpop_task_stream(task_id=str(self.task.id), timeout_seconds=10)

        self.assertIsNone(message)

    @patch("apps.node.services.internal.task._schedule_agent_task_redelivery")
    @patch("apps.node.services.internal.task.redis_store.get_agent_location")
    @patch("apps.node.services.internal.task.redis_store.get_redis")
    def test_deliver_waits_when_agent_location_is_stale_but_recently_seen(
        self,
        mock_get_redis,
        mock_get_agent_location,
        mock_schedule_redelivery,
    ):
        class RedisClient:
            def exists(self, key):
                return False

            def set(self, *args, **kwargs):
                return True

        self.task.status = NodeTask.Status.PENDING
        self.task.save(update_fields=["status"])
        mock_get_agent_location.return_value = "stale-ws"
        mock_get_redis.return_value = RedisClient()

        task = deliver_agent_task(task=self.task)

        self.assertEqual(task.status, NodeTask.Status.PENDING)
        self.assertEqual(task.last_error, "agent websocket is reconnecting")
        mock_schedule_redelivery.assert_called_once()

    @patch("apps.node.services.internal.task.redis_store.push_task_stream")
    @patch("apps.node.services.internal.task.redis_store.clear_agent_location")
    @patch("apps.node.services.internal.task.redis_store.get_agent_location")
    @patch("apps.node.services.internal.task.redis_store.get_redis")
    def test_deliver_fails_when_agent_location_is_stale_beyond_task_grace(
        self,
        mock_get_redis,
        mock_get_agent_location,
        mock_clear_agent_location,
        mock_push_task_stream,
    ):
        class RedisClient:
            def exists(self, key):
                return False

        NodeTask.objects.filter(pk=self.task.pk).update(
            created_at=timezone.now() - timezone.timedelta(seconds=10),
            status=NodeTask.Status.PENDING,
        )
        self.task.refresh_from_db()
        mock_get_agent_location.return_value = "stale-ws"
        mock_get_redis.return_value = RedisClient()

        task = deliver_agent_task(task=self.task)

        self.assertEqual(task.status, NodeTask.Status.FAILED)
        self.assertEqual(task.last_error, "agent websocket is not routable")
        self.node.refresh_from_db()
        self.assertEqual(self.node.status, Node.Status.ONLINE)
        mock_clear_agent_location.assert_called_once_with(agent_id=self.node.id)
        mock_push_task_stream.assert_called_once()

    @patch("apps.node.services.internal.task.redis_store.push_task_stream")
    @patch("apps.node.services.internal.task.redis_store.clear_agent_location")
    @patch("apps.node.services.internal.task.redis_store.get_agent_location")
    @patch("apps.node.services.internal.task.redis_store.get_redis")
    def test_deliver_fails_immediately_when_node_is_offline(
        self,
        mock_get_redis,
        mock_get_agent_location,
        mock_clear_agent_location,
        mock_push_task_stream,
    ):
        class RedisClient:
            def exists(self, key):
                return False

        self.node.status = Node.Status.OFFLINE
        self.node.save(update_fields=["status"])
        self.task.status = NodeTask.Status.PENDING
        self.task.save(update_fields=["status"])
        self.task.refresh_from_db()
        mock_get_agent_location.return_value = "stale-ws"
        mock_get_redis.return_value = RedisClient()

        task = deliver_agent_task(task=self.task)

        self.assertEqual(task.status, NodeTask.Status.FAILED)
        self.assertEqual(task.last_error, "agent websocket is not routable")
        mock_clear_agent_location.assert_called_once_with(agent_id=self.node.id)
        mock_push_task_stream.assert_called_once()

    @patch("apps.node.services.internal.task._send_task_command")
    @patch("apps.node.services.internal.task.redis_store.get_agent_location")
    @patch("apps.node.services.internal.task.redis_store.get_redis")
    def test_redeliver_pending_task_sends_when_route_recovers(
        self,
        mock_get_redis,
        mock_get_agent_location,
        mock_send_task_command,
    ):
        class RedisClient:
            def exists(self, key):
                return True

            def set(self, *args, **kwargs):
                return True

        self.task.status = NodeTask.Status.PENDING
        self.task.last_error = "agent websocket is reconnecting"
        self.task.save(update_fields=["status", "last_error"])
        mock_get_agent_location.return_value = "live-ws"
        mock_get_redis.return_value = RedisClient()

        task = redeliver_pending_agent_task(task_id=self.task.id)

        self.assertIsNotNone(task)
        self.assertEqual(task.status, NodeTask.Status.RUNNING)
        mock_send_task_command.assert_called_once()

    @patch("apps.node.services.internal.task._send_task_command")
    def test_redeliver_terminal_task_is_noop(self, mock_send_task_command):
        self.task.status = NodeTask.Status.SUCCESS
        self.task.save(update_fields=["status"])

        task = redeliver_pending_agent_task(task_id=self.task.id)

        self.assertIsNotNone(task)
        self.assertEqual(task.status, NodeTask.Status.SUCCESS)
        mock_send_task_command.assert_not_called()
