"""Read-only Redis backlog snapshot shared by metrics and Platform Ops."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from redis.exceptions import RedisError, ResponseError

from apps.node.services.internal import redis_store
from apps.node.ws.uplink_queue import (
    NODE_UPLINK_DEAD_LETTER_STREAM,
    NODE_UPLINK_STREAM,
    UPLINK_INGEST_GROUP,
    stream_entry_age_seconds,
)


QUEUE_DEPTH_WARNING = 500
UPLINK_PENDING_AGE_WARNING_SECONDS = 60


def _queue_names() -> list[str]:
    queues = getattr(settings, "CELERY_TASK_QUEUES", ())
    names = {str(getattr(queue, "name", queue)) for queue in queues}
    return sorted(name for name in names if name)


def runtime_backlog_snapshot() -> dict[str, Any]:
    """Return queue depths and Agent uplink lag without raising probe errors."""
    client = redis_store.get_redis()
    if client is None:
        return {
            "status": "error",
            "error": "Redis is unavailable.",
            "queue_depths": {},
            "uplink_stream_length": 0,
            "uplink_pending": 0,
            "uplink_dead_letter": 0,
            "uplink_oldest_pending_seconds": 0.0,
            "warnings": ["Redis backlog metrics are unavailable."],
        }
    try:
        queue_depths = {
            queue_name: int(client.llen(queue_name)) for queue_name in _queue_names()
        }
        stream_length = int(client.xlen(NODE_UPLINK_STREAM))
        dead_letter_count = int(client.xlen(NODE_UPLINK_DEAD_LETTER_STREAM))
        try:
            pending = client.xpending(NODE_UPLINK_STREAM, UPLINK_INGEST_GROUP)
        except ResponseError as exc:
            if "NOGROUP" not in str(exc).upper():
                raise
            pending = {"pending": 0}
        pending_count = int((pending or {}).get("pending", 0))
        oldest_seconds = 0.0
        if pending_count:
            oldest_seconds = stream_entry_age_seconds(
                str((pending or {}).get("min") or "")
            )
    except (RedisError, TypeError, ValueError) as exc:
        return {
            "status": "error",
            "error": type(exc).__name__,
            "queue_depths": {},
            "uplink_stream_length": 0,
            "uplink_pending": 0,
            "uplink_dead_letter": 0,
            "uplink_oldest_pending_seconds": 0.0,
            "warnings": ["Redis backlog metrics could not be collected."],
        }

    warnings = [
        f"Celery queue {name} depth is {depth}."
        for name, depth in queue_depths.items()
        if depth >= QUEUE_DEPTH_WARNING
    ]
    if oldest_seconds >= UPLINK_PENDING_AGE_WARNING_SECONDS:
        warnings.append(
            f"Agent uplink projection is {int(oldest_seconds)} seconds behind."
        )
    if dead_letter_count:
        warnings.append(
            f"Agent uplink dead-letter stream contains {dead_letter_count} entries."
        )
    return {
        "status": "degraded" if warnings else "ok",
        "error": None,
        "queue_depths": queue_depths,
        "uplink_stream_length": stream_length,
        "uplink_pending": pending_count,
        "uplink_dead_letter": dead_letter_count,
        "uplink_oldest_pending_seconds": oldest_seconds,
        "warnings": warnings,
    }
