"""
Redis helpers for node communication (agent_loc, task_stream, task_info).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis
from redis.exceptions import TimeoutError as RedisTimeoutError
from django.conf import settings

from apps.node import conf as node_conf

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def _broker_url() -> str:
    return getattr(settings, "CELERY_BROKER_URL", "redis://redis:6379/0")


def get_redis() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    try:
        _client = redis.Redis.from_url(
            _broker_url(),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=None,
        )
        _client.ping()
        return _client
    except Exception as exc:
        logger.warning("node redis unavailable: %s", exc)
        return None


def agent_loc_key(agent_id: int) -> str:
    return f"agent_loc:{agent_id}"


def _encode_agent_loc(*, ws_instance_id: str, session_id: str) -> str:
    return json.dumps(
        {"ws": ws_instance_id, "session": session_id},
        ensure_ascii=False,
    )


def _decode_agent_loc(raw: str) -> tuple[str | None, str | None]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw, None
    if not isinstance(payload, dict):
        return raw, None
    ws = payload.get("ws")
    session = payload.get("session")
    ws_text = str(ws).strip() if ws else None
    session_text = str(session).strip() if session else None
    return ws_text or None, session_text or None


def set_agent_location(
    *,
    agent_id: int,
    ws_instance_id: str | None = None,
    session_id: str | None = None,
) -> None:
    r = get_redis()
    if r is None:
        return
    ws_id = ws_instance_id or node_conf.WS_INSTANCE_ID
    value = (
        _encode_agent_loc(ws_instance_id=ws_id, session_id=session_id)
        if session_id
        else ws_id
    )
    r.set(agent_loc_key(agent_id), value, ex=node_conf.AGENT_LOC_TTL_SECONDS)


def touch_agent_location(*, agent_id: int) -> None:
    r = get_redis()
    if r is None:
        return
    r.expire(agent_loc_key(agent_id), node_conf.AGENT_LOC_TTL_SECONDS)


def ensure_agent_location_on_heartbeat(*, agent_id: int, session_id: str) -> None:
    """
    Refresh ``agent_loc`` during an open WSS session.

    ``expire`` alone is insufficient when the lease TTL elapsed while the TCP
    session stayed up (for example under ingest back-pressure). Recreate the key
    so unrelated agents are not shown as reconnecting.
    """
    r = get_redis()
    if r is None:
        return
    key = agent_loc_key(agent_id)
    if r.exists(key):
        r.expire(key, node_conf.AGENT_LOC_TTL_SECONDS)
    else:
        set_agent_location(agent_id=agent_id, session_id=session_id)


def get_agent_location(*, agent_id: int) -> str | None:
    r = get_redis()
    if r is None:
        return None
    value = r.get(agent_loc_key(agent_id))
    if not value:
        return None
    ws_instance, _session = _decode_agent_loc(str(value))
    return ws_instance


def clear_agent_location(*, agent_id: int) -> None:
    r = get_redis()
    if r is None:
        return
    r.delete(agent_loc_key(agent_id))


def clear_ws_instance_routes(*, ws_instance_id: str | None = None) -> dict[str, int]:
    """
    Remove stale routing keys owned by one WebSocket process instance.

    Called when a Daphne/WS process starts. If Redis survived a control-plane
    restart, old ``agent_loc`` keys may still point at the same instance id even
    though the Channels groups and TCP sessions are gone.
    """

    ws_id = (ws_instance_id or node_conf.WS_INSTANCE_ID or "").strip()
    if not ws_id:
        return {"agent_locations_deleted": 0, "ws_alive_deleted": 0}
    r = get_redis()
    if r is None:
        return {"agent_locations_deleted": 0, "ws_alive_deleted": 0}

    agent_keys: list[str] = []
    for key in r.scan_iter(match="agent_loc:*", count=500):
        raw = r.get(key)
        if not raw:
            continue
        owner_ws, _session = _decode_agent_loc(str(raw))
        if owner_ws == ws_id:
            agent_keys.append(str(key))

    deleted_agent = 0
    if agent_keys:
        deleted_agent = int(r.delete(*agent_keys) or 0)
    deleted_alive = int(r.delete(ws_alive_key(ws_id)) or 0)
    return {
        "agent_locations_deleted": deleted_agent,
        "ws_alive_deleted": deleted_alive,
    }


def clear_agent_location_if_session(
    *,
    agent_id: int,
    session_id: str,
) -> bool:
    """
    Remove ``agent_loc`` when it still belongs to ``session_id``.

    Returns True when this session owned the key (or Redis is unavailable).
    """
    r = get_redis()
    if r is None:
        return True
    key = agent_loc_key(agent_id)
    raw = r.get(key)
    if not raw:
        return True
    _ws_instance, owner_session = _decode_agent_loc(str(raw))
    if owner_session and owner_session != session_id:
        return False
    r.delete(key)
    return True


def ws_alive_key(ws_instance_id: str) -> str:
    return f"node_alive:{ws_instance_id}"


def touch_ws_instance_alive() -> None:
    r = get_redis()
    if r is None:
        return
    ws_id = node_conf.WS_INSTANCE_ID
    r.set(ws_alive_key(ws_id), "1", ex=node_conf.WS_INSTANCE_ALIVE_TTL_SECONDS)


def task_stream_key(task_id: str) -> str:
    return f"task_stream:{task_id}"


def task_info_key(task_id: str) -> str:
    return f"task_info:{task_id}"


def push_task_stream(*, task_id: str, message: dict[str, Any]) -> None:
    r = get_redis()
    if r is None:
        return
    r.lpush(task_stream_key(task_id), json.dumps(message, ensure_ascii=False))


def bpop_task_stream(*, task_id: str, timeout_seconds: int = 15) -> dict[str, Any] | None:
    r = get_redis()
    if r is None:
        return None
    try:
        item = r.blpop(task_stream_key(task_id), timeout=max(1, int(timeout_seconds)))
    except RedisTimeoutError as exc:
        logger.warning("node redis task stream wait timed out for task %s: %s", task_id, exc)
        return None
    if not item:
        return None
    _, raw = item
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def set_task_info(*, task_id: str, data: dict[str, Any], ttl_seconds: int = 3600) -> None:
    r = get_redis()
    if r is None:
        return
    r.set(
        task_info_key(task_id),
        json.dumps(data, ensure_ascii=False),
        ex=max(60, int(ttl_seconds)),
    )


def get_task_info(*, task_id: str) -> dict[str, Any] | None:
    r = get_redis()
    if r is None:
        return None
    raw = r.get(task_info_key(task_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
