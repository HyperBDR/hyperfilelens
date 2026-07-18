"""
Redis stream queue for Agent WebSocket uplink follow-up (heartbeat inventory, task frames).

The Daphne hot path only touches ``agent_loc`` and enqueues payloads here; Celery
workers drain the stream and persist to PostgreSQL.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.exceptions import ResponseError

from apps.node import conf as node_conf
from apps.node.services.internal import redis_store
from apps.node.ws.wire import ParsedUplink, WireType

logger = logging.getLogger(__name__)

NODE_UPLINK_STREAM = "node:uplink:stream"
UPLINK_INGEST_GROUP = "node-uplink-ingest"
UPLINK_INGEST_CONSUMER = "worker"


def _redis():
    return redis_store.get_redis()


def ensure_uplink_stream_group() -> None:
    r = _redis()
    if r is None:
        return
    try:
        r.xgroup_create(
            NODE_UPLINK_STREAM,
            UPLINK_INGEST_GROUP,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def touch_heartbeat_fast(*, node_id: int, session_id: str) -> None:
    """Hot path: refresh Redis routing only (no PostgreSQL)."""
    redis_store.ensure_agent_location_on_heartbeat(
        agent_id=node_id,
        session_id=session_id,
    )
    redis_store.touch_ws_instance_alive()


def _serialize_uplink(*, node_id: int, message: ParsedUplink) -> dict[str, str]:
    payload: dict[str, Any] = {
        "node_id": node_id,
        "msg_type": str(message.msg_type),
    }
    if message.msg_type == WireType.HEARTBEAT:
        payload["heartbeat_payload"] = message.heartbeat_payload
    else:
        payload["task_id"] = message.task_id
        payload["progress"] = message.progress
        payload["is_alive"] = message.is_alive
        payload["status"] = message.status
        payload["result"] = message.result
        payload["error"] = message.error
    return {"payload": json.dumps(payload, ensure_ascii=False)}


def enqueue_uplink(*, node_id: int, message: ParsedUplink) -> None:
    r = _redis()
    if r is None:
        from apps.node.tasks.uplink_ingest import process_uplink_payload

        process_uplink_payload.delay(payload=_serialize_uplink(node_id=node_id, message=message)["payload"])
        return
    ensure_uplink_stream_group()
    r.xadd(NODE_UPLINK_STREAM, _serialize_uplink(node_id=node_id, message=message))


def _deserialize_payload(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def payload_to_parsed(data: dict[str, Any]) -> tuple[int, ParsedUplink] | None:
    node_id_raw = data.get("node_id")
    if not isinstance(node_id_raw, int):
        try:
            node_id = int(node_id_raw)
        except (TypeError, ValueError):
            return None
    else:
        node_id = node_id_raw

    msg_type_raw = str(data.get("msg_type", "")).strip().lower()
    try:
        msg_type = WireType(msg_type_raw)
    except ValueError:
        return None

    if msg_type == WireType.HEARTBEAT:
        hb = data.get("heartbeat_payload")
        heartbeat_payload = hb if isinstance(hb, dict) else None
        return node_id, ParsedUplink(msg_type=msg_type, heartbeat_payload=heartbeat_payload)

    task_id = data.get("task_id")
    if not task_id:
        return None
    return node_id, ParsedUplink(
        msg_type=msg_type,
        task_id=str(task_id),
        progress=data.get("progress") if isinstance(data.get("progress"), dict) else None,
        is_alive=bool(data.get("is_alive")),
        status=str(data.get("status") or "") or None,
        result=data.get("result") if isinstance(data.get("result"), dict) else None,
        error=str(data.get("error") or ""),
    )


def drain_uplink_stream(*, count: int | None = None) -> int:
    """
    Consume up to ``count`` uplink entries from Redis and return processed count.

    Falls back to zero when Redis is unavailable.
    """
    r = _redis()
    if r is None:
        return 0

    batch = max(1, int(count or node_conf.UPLINK_INGEST_BATCH_SIZE))
    ensure_uplink_stream_group()

    try:
        rows = r.xreadgroup(
            UPLINK_INGEST_GROUP,
            UPLINK_INGEST_CONSUMER,
            {NODE_UPLINK_STREAM: ">"},
            count=batch,
            block=1,
        )
    except ResponseError:
        ensure_uplink_stream_group()
        rows = r.xreadgroup(
            UPLINK_INGEST_GROUP,
            UPLINK_INGEST_CONSUMER,
            {NODE_UPLINK_STREAM: ">"},
            count=batch,
            block=1,
        )

    if not rows:
        return 0

    from apps.node.ws.uplink import handle_uplink

    processed = 0
    for _stream, messages in rows:
        for entry_id, fields in messages:
            raw = fields.get("payload") if isinstance(fields, dict) else None
            if not raw:
                r.xack(NODE_UPLINK_STREAM, UPLINK_INGEST_GROUP, entry_id)
                continue
            data = _deserialize_payload(str(raw))
            if data is None:
                r.xack(NODE_UPLINK_STREAM, UPLINK_INGEST_GROUP, entry_id)
                continue
            parsed = payload_to_parsed(data)
            if parsed is None:
                r.xack(NODE_UPLINK_STREAM, UPLINK_INGEST_GROUP, entry_id)
                continue
            node_id, message = parsed
            try:
                handle_uplink(node_id=node_id, message=message)
                processed += 1
            except Exception:
                logger.exception("uplink ingest failed node_id=%s msg_type=%s", node_id, message.msg_type)
            r.xack(NODE_UPLINK_STREAM, UPLINK_INGEST_GROUP, entry_id)
    return processed
