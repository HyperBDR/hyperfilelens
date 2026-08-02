"""Best-effort Redis/Celery runtime metrics for operational alerting."""

from __future__ import annotations

from prometheus_client import Gauge

from common.ops.runtime_backlog import runtime_backlog_snapshot


QUEUE_DEPTH = Gauge(
    "hfl_celery_queue_depth",
    "Number of messages waiting in a Celery Redis queue.",
    ("queue",),
)
UPLINK_STREAM_LENGTH = Gauge(
    "hfl_node_uplink_stream_length",
    "Number of entries retained in the Agent uplink Redis stream.",
)
UPLINK_PENDING = Gauge(
    "hfl_node_uplink_pending",
    "Number of Agent uplink entries pending acknowledgement.",
)
UPLINK_DEAD_LETTER = Gauge(
    "hfl_node_uplink_dead_letter",
    "Number of Agent uplink entries quarantined for manual replay.",
)
UPLINK_OLDEST_PENDING_SECONDS = Gauge(
    "hfl_node_uplink_oldest_pending_seconds",
    "Age of the oldest pending Agent uplink projection.",
)
RUNTIME_METRICS_COLLECTION_SUCCESS = Gauge(
    "hfl_runtime_metrics_collection_success",
    "Whether the last Redis runtime metrics collection succeeded.",
)


def collect_runtime_metrics() -> None:
    """Refresh queue and uplink gauges without failing the metrics endpoint."""
    snapshot = runtime_backlog_snapshot()
    if snapshot["status"] == "error":
        RUNTIME_METRICS_COLLECTION_SUCCESS.set(0)
        return
    for queue_name, depth in snapshot["queue_depths"].items():
        QUEUE_DEPTH.labels(queue=queue_name).set(depth)
    UPLINK_STREAM_LENGTH.set(snapshot["uplink_stream_length"])
    UPLINK_PENDING.set(snapshot["uplink_pending"])
    UPLINK_DEAD_LETTER.set(snapshot["uplink_dead_letter"])
    UPLINK_OLDEST_PENDING_SECONDS.set(snapshot["uplink_oldest_pending_seconds"])
    RUNTIME_METRICS_COLLECTION_SUCCESS.set(1)
