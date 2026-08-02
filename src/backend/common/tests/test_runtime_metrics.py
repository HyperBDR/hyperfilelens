"""Tests for best-effort Redis queue and Agent uplink metrics."""

from unittest.mock import patch

from django.test import SimpleTestCase

from common.ops import runtime_metrics


class RuntimeMetricsTests(SimpleTestCase):
    @patch.object(runtime_metrics, "runtime_backlog_snapshot")
    def test_collects_queue_and_uplink_backlog(self, snapshot) -> None:
        snapshot.return_value = {
            "status": "ok",
            "queue_depths": {"backend": 7},
            "uplink_stream_length": 12,
            "uplink_pending": 2,
            "uplink_dead_letter": 1,
            "uplink_oldest_pending_seconds": 4.5,
        }

        runtime_metrics.collect_runtime_metrics()

        self.assertEqual(
            runtime_metrics.QUEUE_DEPTH.labels(queue="backend")._value.get(),
            7,
        )
        self.assertEqual(runtime_metrics.UPLINK_STREAM_LENGTH._value.get(), 12)
        self.assertEqual(runtime_metrics.UPLINK_PENDING._value.get(), 2)
        self.assertEqual(runtime_metrics.UPLINK_DEAD_LETTER._value.get(), 1)
        self.assertEqual(
            runtime_metrics.UPLINK_OLDEST_PENDING_SECONDS._value.get(),
            4.5,
        )
        self.assertEqual(
            runtime_metrics.RUNTIME_METRICS_COLLECTION_SUCCESS._value.get(),
            1,
        )

    @patch.object(runtime_metrics, "runtime_backlog_snapshot")
    def test_redis_outage_does_not_break_metrics(self, snapshot) -> None:
        snapshot.return_value = {"status": "error"}
        runtime_metrics.collect_runtime_metrics()

        self.assertEqual(
            runtime_metrics.RUNTIME_METRICS_COLLECTION_SUCCESS._value.get(),
            0,
        )
