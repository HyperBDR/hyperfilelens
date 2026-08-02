"""Tests for Platform Ops queue and uplink backlog snapshots."""

from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from redis.exceptions import ResponseError

from common.ops import runtime_backlog


class RuntimeBacklogTests(SimpleTestCase):
    @patch.object(runtime_backlog.redis_store, "get_redis")
    @patch.object(runtime_backlog, "stream_entry_age_seconds", return_value=90.0)
    def test_large_or_old_backlog_is_degraded(self, entry_age, get_redis) -> None:
        redis = Mock()
        redis.llen.side_effect = lambda name: 700 if name == "node.ingest" else 0
        redis.xlen.side_effect = (
            lambda name: 30 if name == runtime_backlog.NODE_UPLINK_STREAM else 0
        )
        redis.xpending.return_value = {"pending": 4, "min": "1000-0"}
        get_redis.return_value = redis

        snapshot = runtime_backlog.runtime_backlog_snapshot()

        self.assertEqual(snapshot["status"], "degraded")
        self.assertEqual(snapshot["queue_depths"]["node.ingest"], 700)
        self.assertEqual(snapshot["uplink_oldest_pending_seconds"], 90.0)
        self.assertEqual(len(snapshot["warnings"]), 2)
        entry_age.assert_called_once_with("1000-0")

    @patch.object(runtime_backlog.redis_store, "get_redis")
    def test_dead_letters_degrade_backlog_health(self, get_redis) -> None:
        redis = Mock()
        redis.llen.return_value = 0
        redis.xlen.side_effect = (
            lambda name: 3
            if name == runtime_backlog.NODE_UPLINK_DEAD_LETTER_STREAM
            else 0
        )
        redis.xpending.side_effect = ResponseError("NOGROUP no such key")
        get_redis.return_value = redis

        snapshot = runtime_backlog.runtime_backlog_snapshot()

        self.assertEqual(snapshot["status"], "degraded")
        self.assertEqual(snapshot["uplink_dead_letter"], 3)
        self.assertIn("dead-letter", snapshot["warnings"][0])

    @patch.object(runtime_backlog.redis_store, "get_redis", return_value=None)
    def test_redis_outage_returns_sanitized_error(self, _get_redis) -> None:
        snapshot = runtime_backlog.runtime_backlog_snapshot()

        self.assertEqual(snapshot["status"], "error")
        self.assertEqual(snapshot["error"], "Redis is unavailable.")

    @patch.object(runtime_backlog.redis_store, "get_redis")
    def test_missing_uplink_group_is_an_empty_healthy_queue(self, get_redis) -> None:
        redis = Mock()
        redis.llen.return_value = 0
        redis.xlen.return_value = 0
        redis.xpending.side_effect = ResponseError("NOGROUP no such key")
        get_redis.return_value = redis

        snapshot = runtime_backlog.runtime_backlog_snapshot()

        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["uplink_pending"], 0)
        self.assertEqual(snapshot["uplink_dead_letter"], 0)
