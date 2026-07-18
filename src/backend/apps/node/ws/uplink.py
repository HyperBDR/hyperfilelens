"""
Agent WebSocket session and uplink for lifecycle and task frames.
"""

from __future__ import annotations

import logging

from django.db import DatabaseError
from django.utils import timezone

from apps.node import conf as node_conf
from apps.node.models import Node, NodeTask
from apps.node.services.internal import redis_store
from apps.node.services.internal.agent_log import task_log_context
from apps.node.services.internal.node_naming import (
    resolve_inventory_node_name,
    uniquify_node_name,
)
from apps.node.services.interface import (
    complete_task,
    record_task_progress,
)
from apps.node.ws.wire import ParsedUplink, WireType
from apps.source.services.internal.agent_host_sync import sync_agent_source_host_by_id

logger = logging.getLogger(__name__)


def on_agent_connected(*, node_id: int, session_id: str, client_ip: str | None = None) -> None:
    redis_store.set_agent_location(agent_id=node_id, session_id=session_id)
    redis_store.touch_ws_instance_alive()
    updates: dict = {
        "last_seen_at": timezone.now(),
        "status": Node.Status.ONLINE,
    }
    if client_ip:
        updates["ip_address"] = client_ip
    Node.objects.filter(pk=node_id).update(**updates)
    try:
        sync_agent_source_host_by_id(node_id=node_id)
    except Exception:
        logger.debug("agent source-host sync failed node_id=%s", node_id, exc_info=True)
    logger.info(
        "agent ws connected node_id=%s session=%s client_ip=%s",
        node_id,
        session_id,
        client_ip or "-",
    )
    _schedule_lifecycle_advance(node_id=node_id)


def on_agent_disconnected(*, node_id: int, session_id: str) -> None:
    if not redis_store.clear_agent_location_if_session(
        agent_id=node_id,
        session_id=session_id,
    ):
        logger.info(
            "agent ws disconnected ignored (superseded session) node_id=%s session=%s",
            node_id,
            session_id,
        )
        return

    try:
        sync_agent_source_host_by_id(node_id=node_id)
    except Exception:
        logger.debug("agent source-host sync failed node_id=%s", node_id, exc_info=True)
    logger.info(
        "agent ws disconnected node_id=%s session=%s",
        node_id,
        session_id,
    )
    _schedule_lifecycle_advance(node_id=node_id)


def _schedule_lifecycle_advance(*, node_id: int) -> None:
    from apps.node.tasks.lifecycle import advance_node_lifecycle_for_node

    advance_node_lifecycle_for_node.delay(node_id=int(node_id))


def handle_uplink(*, node_id: int, message: ParsedUplink) -> None:
    if message.msg_type == WireType.HEARTBEAT:
        _process_heartbeat_followup(node_id=node_id, inventory=message.heartbeat_payload)
        return

    if message.msg_type in (WireType.TASK_PROGRESS, WireType.TASK_ALIVE):
        _handle_task_progress(node_id=node_id, message=message)
        return

    if message.msg_type == WireType.TASK_RESULT:
        _handle_task_result(node_id=node_id, message=message)


def _inventory_throttle_key(*, node_id: int) -> str:
    return f"heartbeat_inv_throttle:{node_id}"


def _merge_heartbeat_inventory_updates(*, node: Node, inventory: dict) -> dict:
    """Build ``Node.objects.update`` kwargs for inventory snapshot fields (not metrics)."""
    updates: dict = {}
    inv_only = {k: v for k, v in inventory.items() if k != "metrics"}
    if ver := str(inventory.get("agent_version") or "").strip():
        updates["version"] = ver
    if inv_only:
        meta = dict(node.metadata or {})
        meta["inventory"] = {**dict(meta.get("inventory") or {}), **inv_only}
        suggested = resolve_inventory_node_name(node=node, inventory=inv_only)
        if suggested:
            updates["name"] = uniquify_node_name(
                organization_id=node.organization_id,
                name=suggested,
                exclude_node_id=node.id,
            )
        updates["metadata"] = meta
    return updates


def apply_heartbeat_inventory_snapshot(*, node_id: int, inventory: dict | None) -> None:
    """Hot path: persist list/detail inventory fields without waiting for Celery ingest."""
    if not inventory:
        return
    node = Node.objects.filter(pk=node_id).first()
    if node is None:
        return
    updates = _merge_heartbeat_inventory_updates(node=node, inventory=inventory)
    if not updates:
        return
    updates["last_seen_at"] = timezone.now()
    updates["status"] = Node.Status.ONLINE
    Node.objects.filter(pk=node_id).update(**updates)


def _should_process_full_inventory(*, node_id: int) -> bool:
    r = redis_store.get_redis()
    if r is None:
        return True
    key = _inventory_throttle_key(node_id=node_id)
    if r.exists(key):
        return False
    r.set(key, "1", ex=max(60, int(node_conf.HEARTBEAT_INVENTORY_MIN_INTERVAL_SECONDS)))
    return True


def _process_heartbeat_followup(*, node_id: int, inventory: dict | None = None) -> None:
    redis_store.touch_agent_location(agent_id=node_id)
    redis_store.touch_ws_instance_alive()
    node = Node.objects.filter(pk=node_id).first()
    if node is None:
        return

    full_inventory = inventory and _should_process_full_inventory(node_id=node_id)
    updates: dict = {
        "last_seen_at": timezone.now(),
        "status": Node.Status.ONLINE,
    }
    if full_inventory:
        updates.update(_merge_heartbeat_inventory_updates(node=node, inventory=inventory))
    Node.objects.filter(pk=node_id).update(**updates)

    if (
        full_inventory
        and inventory
        and isinstance(inventory.get("metrics"), dict)
        and inventory["metrics"]
    ):
        from apps.monitor.services.internal.node_metrics import ingest_node_monitor_sample

        fresh = Node.objects.filter(pk=node_id).first()
        if fresh is not None:
            ingest_node_monitor_sample(node=fresh, sample=inventory["metrics"])

    if full_inventory:
        try:
            sync_agent_source_host_by_id(node_id=node_id)
        except Exception:
            logger.debug("agent source-host sync failed node_id=%s", node_id, exc_info=True)


def _handle_task_progress(*, node_id: int, message: ParsedUplink) -> None:
    if not message.task_id:
        return
    try:
        task = record_task_progress(
            task_id=message.task_id,
            node_id=node_id,
            progress=message.progress or {},
            alive=message.is_alive,
        )
    except LookupError:
        logger.debug(
            "agent task progress ignored (unknown task) %s",
            task_log_context(node_id=node_id, task_id=message.task_id),
        )
        return
    except DatabaseError as exc:
        logger.warning(
            "agent task progress persist failed %s error=%s",
            task_log_context(node_id=node_id, task_id=message.task_id),
            exc,
        )
        return
    try:
        from apps.protection.services.backup_orchestrator import (
            maybe_trigger_backup_advance,
            reattach_backup_node_task,
        )

        if task.status == NodeTask.Status.TIMEOUT:
            reattached = reattach_backup_node_task(node_task=task)
            if reattached is not None:
                task = reattached
        maybe_trigger_backup_advance(node_task=task)
        try:
            from apps.restore.services.restore_progress import maybe_trigger_restore_progress

            maybe_trigger_restore_progress(node_task=task)
        except Exception:
            logger.debug("restore progress after progress failed task_id=%s", message.task_id, exc_info=True)
    except Exception:
        logger.debug("backup advance after progress failed task_id=%s", message.task_id, exc_info=True)


def _handle_task_result(*, node_id: int, message: ParsedUplink) -> None:
    if not message.task_id:
        return
    ctx = task_log_context(
        node_id=node_id,
        task_id=message.task_id,
        kind=str(message.status or ""),
    )
    try:
        task = complete_task(
            task_id=message.task_id,
            node_id=node_id,
            status=message.status or "success",
            result=message.result or {},
            error=message.error,
        )
        try:
            from apps.protection.services.backup_orchestrator import maybe_trigger_backup_advance

            maybe_trigger_backup_advance(node_task=task)
        except Exception:
            logger.debug(
                "backup advance after result failed task_id=%s",
                message.task_id,
                exc_info=True,
            )
        try:
            from apps.restore.services.restore_progress import maybe_trigger_restore_progress

            maybe_trigger_restore_progress(node_task=task)
        except Exception:
            logger.debug(
                "restore progress after result failed task_id=%s",
                message.task_id,
                exc_info=True,
            )
        logger.info(
            "agent task result received %s status=%s",
            task_log_context(node_id=node_id, task_id=message.task_id, kind=task.kind),
            task.status,
        )
    except LookupError:
        logger.debug("agent task result ignored (unknown task) %s", ctx)
    except DatabaseError as exc:
        logger.warning("agent task result persist failed %s error=%s", ctx, exc)
    except Exception:
        logger.exception("agent task result handling failed %s", ctx)
