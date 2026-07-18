"""
NodeTask write path: create, deliver, progress, complete, and watchdog sweep.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.iam.models import Organization
from apps.node import conf as node_conf
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.node.services.internal import redis_store
from apps.node.services.internal.agent_log import task_log_context

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (NodeTask.Status.PENDING, NodeTask.Status.RUNNING)
_TERMINAL_STATUSES = frozenset(
    {
        NodeTask.Status.SUCCESS,
        NodeTask.Status.FAILED,
        NodeTask.Status.TIMEOUT,
        NodeTask.Status.CANCELED,
    },
)


@dataclass(frozen=True)
class DispatchResult:
    task: NodeTask


class _RouteState(StrEnum):
    ONLINE = "online"
    RECONNECTING = "reconnecting"
    OFFLINE = "offline"


def _watchdog_deadline(*, from_time: datetime | None = None) -> datetime:
    base = from_time or timezone.now()
    return base + timezone.timedelta(seconds=node_conf.TASK_WATCHDOG_SECONDS)


def _protection_backup_watchdog_deadline(*, from_time: datetime | None = None) -> datetime:
    from apps.protection import conf as protection_conf

    base = from_time or timezone.now()
    return base + timezone.timedelta(
        seconds=protection_conf.PROTECTION_BACKUP_NODE_TASK_WATCHDOG_SECONDS
    )


def _lifecycle_detached_watchdog_deadline(*, from_time: datetime | None = None) -> datetime:
    base = from_time or timezone.now()
    return base + timezone.timedelta(seconds=node_conf.LIFECYCLE_DETACHED_TIMEOUT_SECONDS)


def _is_protection_backup_task(task: NodeTask) -> bool:
    from apps.protection import conf as protection_conf

    return (
        task.correlation_type == protection_conf.PROTECTION_BACKUP_CORRELATION_TYPE
        and task.kind == "backup.run"
    )


def _substantive_backup_progress(progress: dict[str, Any] | None) -> bool:
    if not isinstance(progress, dict) or not progress:
        return False
    for key in ("hashed_bytes", "uploaded_bytes", "kopia_percent", "percent"):
        if progress.get(key) not in (None, ""):
            return True
    phase = str(progress.get("kopia_phase") or progress.get("phase") or "").strip().lower()
    return phase in {
        "hashing",
        "uploading",
        "restoring",
        "snapshot_created",
        "restore_completed",
        "repository_ready",
        "snapshot_start",
        "kopia_snapshot",
        "kopia_transfer",
    }


def _initial_watchdog_deadline(
    *,
    correlation_type: str,
    from_time: datetime | None = None,
    kind: str = "",
) -> datetime:
    if correlation_type == node_conf.LIFECYCLE_CORRELATION_TYPE:
        return _lifecycle_detached_watchdog_deadline(from_time=from_time)
    from apps.protection import conf as protection_conf

    if (
        correlation_type == protection_conf.PROTECTION_BACKUP_CORRELATION_TYPE
        and kind == "backup.run"
    ):
        return _protection_backup_watchdog_deadline(from_time=from_time)
    return _watchdog_deadline(from_time=from_time)


def _is_lifecycle_correlated_task(task: NodeTask) -> bool:
    return task.correlation_type == node_conf.LIFECYCLE_CORRELATION_TYPE


def _task_has_detached_marker(task: NodeTask) -> bool:
    if not _is_lifecycle_correlated_task(task):
        return False
    result = task.result if isinstance(task.result, dict) else {}
    if str(result.get("mode") or "").strip() == "local_detached":
        return True
    progress = result.get("last_progress")
    if isinstance(progress, dict):
        return str(progress.get("mode") or "").strip() == "local_detached"
    return False


def _should_apply_progress_update(
    *,
    task: NodeTask,
    incoming: dict[str, Any],
    existing: dict[str, Any] | None,
) -> bool:
    """Ignore generic agent heartbeats once substantive Kopia progress exists."""
    if not _is_protection_backup_task(task):
        return True
    if _substantive_backup_progress(incoming):
        return True
    if not isinstance(existing, dict) or not _substantive_backup_progress(existing):
        return True
    return False


def _merge_progress_into_result(
    *,
    task: NodeTask,
    progress: dict[str, Any],
    merged: dict[str, Any],
    now: datetime,
) -> None:
    existing = merged.get("last_progress")
    if not _should_apply_progress_update(
        task=task,
        incoming=progress,
        existing=existing if isinstance(existing, dict) else None,
    ):
        return
    merged["last_progress"] = progress
    mode = str(progress.get("mode") or "").strip()
    if mode != "local_detached":
        return
    merged["mode"] = mode
    target = str(progress.get("target_version") or "").strip()
    if target:
        merged["target_version"] = target
    if not merged.get("detached_at"):
        merged["detached_at"] = now.isoformat()


def _apply_detached_running_state(*, task: NodeTask, merged: dict[str, Any], now: datetime) -> list[str]:
    extra_fields: list[str] = []
    if str(merged.get("mode") or "").strip() != "local_detached":
        return extra_fields
    if not merged.get("detached_at"):
        merged["detached_at"] = now.isoformat()
        extra_fields.append("result")
    task.watchdog_deadline_at = _lifecycle_detached_watchdog_deadline(from_time=now)
    task.last_progress_at = now
    extra_fields.extend(["watchdog_deadline_at", "last_progress_at"])
    return extra_fields


def _send_task_command(*, task: NodeTask) -> None:
    from apps.node.ws.downlink import send_task_command

    send_task_command(task=task)


def _node_ws_routable(*, node_id: int) -> bool:
    ws_instance = redis_store.get_agent_location(agent_id=node_id)
    if not ws_instance:
        return False
    client = redis_store.get_redis()
    if client is None:
        return True
    return bool(client.exists(redis_store.ws_alive_key(ws_instance)))


def _last_seen_within_task_route_grace(node: Node) -> bool:
    if not node.last_seen_at:
        return False
    grace = timezone.timedelta(seconds=max(0, int(node_conf.NODE_RECONNECT_GRACE_SECONDS)))
    return timezone.now() - node.last_seen_at < grace


def _task_within_route_grace(task: NodeTask) -> bool:
    grace = timezone.timedelta(seconds=max(0, int(node_conf.TASK_ROUTE_RECONNECT_GRACE_SECONDS)))
    return timezone.now() - task.created_at < grace


def _node_route_state(*, task: NodeTask) -> _RouteState:
    node = task.node
    if node.role not in (NodeRole.AGENT, NodeRole.PROXY):
        return _RouteState.ONLINE
    if _node_ws_routable(node_id=node.id):
        return _RouteState.ONLINE
    if (
        node.status == Node.Status.ONLINE
        and _last_seen_within_task_route_grace(node)
        and _task_within_route_grace(task)
    ):
        return _RouteState.RECONNECTING
    return _RouteState.OFFLINE


def _sync_task_info(task: NodeTask) -> None:
    redis_store.set_task_info(
        task_id=str(task.id),
        data={
            "task_id": str(task.id),
            "status": task.status,
            "node_id": task.node_id,
            "kind": task.kind,
            "correlation_type": task.correlation_type,
            "correlation_id": task.correlation_id,
            "last_progress_at": (
                task.last_progress_at.isoformat() if task.last_progress_at else None
            ),
            "watchdog_deadline_at": task.watchdog_deadline_at.isoformat(),
            "result": task.result,
            "last_error": task.last_error,
        },
    )


def _terminal_stream_message(task: NodeTask) -> dict[str, Any]:
    return {
        "task_id": str(task.id),
        "status": task.status,
        "result": task.result,
        "error": task.last_error,
    }


def _schedule_agent_task_redelivery(*, task: NodeTask) -> None:
    from apps.node.tasks.node_task import redeliver_agent_task

    redeliver_agent_task.apply_async(
        kwargs={"task_id": str(task.id)},
        countdown=1,
    )


def _mark_task_reconnecting(*, task: NodeTask) -> NodeTask:
    updated = NodeTask.objects.filter(pk=task.pk, status=NodeTask.Status.PENDING).update(
        last_error="agent websocket is reconnecting",
        updated_at=timezone.now(),
    )
    task.refresh_from_db()
    if updated == 0 or task.status != NodeTask.Status.PENDING:
        _sync_task_info(task)
        return task
    _sync_task_info(task)
    try:
        _schedule_agent_task_redelivery(task=task)
    except Exception:
        logger.warning("failed to schedule agent task redelivery task_id=%s", task.id, exc_info=True)
    logger.info(
        "agent task delivery delayed while websocket reconnects task_id=%s node_id=%s kind=%s",
        task.id,
        task.node_id,
        task.kind,
    )
    return task


def _fail_task_delivery(*, task: NodeTask, reason: str) -> NodeTask:
    NodeTask.objects.filter(pk=task.pk).update(
        status=NodeTask.Status.FAILED,
        last_error=reason[:2000],
        updated_at=timezone.now(),
    )
    task.refresh_from_db()
    redis_store.push_task_stream(
        task_id=str(task.id),
        message=_terminal_stream_message(task),
    )
    return task


def create_agent_task(
    *,
    org: Organization,
    node: Node,
    kind: str,
    payload: dict | None = None,
    correlation_type: str = "",
    correlation_id: str = "",
) -> NodeTask:
    if node.organization_id != org.id:
        raise ValueError("node/org mismatch")

    now = timezone.now()
    task = NodeTask.objects.create(
        organization=org,
        node=node,
        correlation_type=correlation_type or "",
        correlation_id=str(correlation_id or ""),
        kind=kind,
        payload=payload or {},
        status=NodeTask.Status.PENDING,
        watchdog_deadline_at=_initial_watchdog_deadline(
            correlation_type=correlation_type or "",
            from_time=now,
            kind=kind,
        ),
    )
    logger.info(
        "agent task created %s",
        task_log_context(
            node_id=node.id,
            task_id=str(task.id),
            kind=kind,
            correlation_type=correlation_type,
            correlation_id=correlation_id,
        ),
    )
    return task


def deliver_agent_task(*, task: NodeTask) -> NodeTask:
    """Send ``task.command`` to Agent and mark task running (or failed)."""
    if task.status != NodeTask.Status.PENDING:
        return task
    ctx = task_log_context(
        node_id=task.node_id,
        task_id=str(task.id),
        kind=task.kind,
        correlation_type=task.correlation_type,
        correlation_id=task.correlation_id,
    )
    try:
        route_state = _node_route_state(task=task)
        if route_state == _RouteState.RECONNECTING:
            return _mark_task_reconnecting(task=task)
        if route_state == _RouteState.OFFLINE:
            redis_store.clear_agent_location(agent_id=task.node_id)
            raise RuntimeError("agent websocket is not routable")
        logger.info("agent task dispatching %s", ctx)
        _send_task_command(task=task)
        dispatched_at = timezone.now()
        NodeTask.objects.filter(pk=task.pk).update(
            status=NodeTask.Status.RUNNING,
            dispatched_at=dispatched_at,
            last_progress_at=dispatched_at,
            watchdog_deadline_at=_initial_watchdog_deadline(
                correlation_type=task.correlation_type,
                from_time=dispatched_at,
                kind=task.kind,
            ),
        )
        task.refresh_from_db()
        _sync_task_info(task)
        logger.info("agent task dispatched %s status=%s", ctx, task.status)
    except (RuntimeError, OSError) as exc:
        logger.warning(
            "agent task dispatch failed %s error=%s",
            ctx,
            str(exc)[:500],
        )
        task = _fail_task_delivery(task=task, reason=str(exc))
    return task


def redeliver_pending_agent_task(*, task_id: uuid.UUID | str) -> NodeTask | None:
    task = (
        NodeTask.objects.select_related("node")
        .filter(pk=task_id)
        .first()
    )
    if task is None:
        return None
    if task.status != NodeTask.Status.PENDING:
        return task
    delivered = deliver_agent_task(task=task)
    if delivered.status == NodeTask.Status.RUNNING:
        logger.info(
            "agent task redelivery succeeded task_id=%s node_id=%s kind=%s",
            delivered.id,
            delivered.node_id,
            delivered.kind,
        )
    elif delivered.status == NodeTask.Status.FAILED:
        logger.info(
            "agent task redelivery failed task_id=%s node_id=%s kind=%s error=%s",
            delivered.id,
            delivered.node_id,
            delivered.kind,
            delivered.last_error,
        )
    return delivered


@transaction.atomic
def dispatch_task(
    *,
    org: Organization,
    node: Node,
    kind: str,
    payload: dict | None = None,
    correlation_type: str = "",
    correlation_id: str = "",
) -> NodeTask:
    task = create_agent_task(
        org=org,
        node=node,
        kind=kind,
        payload=payload,
        correlation_type=correlation_type,
        correlation_id=correlation_id,
    )
    transaction.on_commit(
        lambda bound_task=task: deliver_agent_task(task=bound_task),
    )
    return task


@transaction.atomic
def record_task_progress(
    *,
    task_id: uuid.UUID | str,
    node_id: int,
    progress: dict[str, Any] | None = None,
    alive: bool = False,
) -> NodeTask:
    task = (
        NodeTask.objects.select_for_update()
        .filter(pk=task_id, node_id=node_id)
        .first()
    )
    if task is None:
        raise LookupError("task not found")

    if task.status not in _ACTIVE_STATUSES:
        return task

    now = timezone.now()
    task.status = NodeTask.Status.RUNNING
    task.last_progress_at = now
    from apps.protection import conf as protection_conf

    if (
        _is_protection_backup_task(task)
        and protection_conf.PROTECTION_BACKUP_DISABLE_SHORT_WATCHDOG
    ):
        if _substantive_backup_progress(progress):
            task.watchdog_deadline_at = _protection_backup_watchdog_deadline(from_time=now)
        update_fields = ["status", "last_progress_at", "result", "updated_at"]
        if _substantive_backup_progress(progress):
            update_fields.append("watchdog_deadline_at")
    else:
        task.watchdog_deadline_at = _watchdog_deadline(from_time=now)
        update_fields = ["status", "last_progress_at", "watchdog_deadline_at", "result", "updated_at"]
    if progress:
        merged = dict(task.result or {})
        _merge_progress_into_result(task=task, progress=progress, merged=merged, now=now)
        task.result = merged
        if _task_has_detached_marker(task):
            update_fields = list(
                dict.fromkeys(update_fields + _apply_detached_running_state(task=task, merged=merged, now=now))
            )
    task.save(update_fields=update_fields)
    _sync_task_info(task)

    stream_msg = {
        "task_id": str(task.id),
        "status": task.status,
        "alive": alive,
        "progress": progress or {},
    }
    redis_store.push_task_stream(task_id=str(task.id), message=stream_msg)
    return task


@transaction.atomic
def complete_task(
    *,
    task_id: uuid.UUID | str,
    node_id: int,
    status: str,
    result: dict[str, Any] | None = None,
    error: str = "",
    replace_result: bool = False,
) -> NodeTask:
    task = (
        NodeTask.objects.select_for_update()
        .filter(pk=task_id, node_id=node_id)
        .first()
    )
    if task is None:
        raise LookupError("task not found")

    if task.status in _TERMINAL_STATUSES:
        incoming = status.lower()
        if task.status == NodeTask.Status.SUCCESS and incoming not in (
            "success",
            "succeeded",
            "ok",
        ):
            return task

    ctx = task_log_context(
        node_id=node_id,
        task_id=str(task_id),
        kind=task.kind,
        correlation_type=task.correlation_type,
        correlation_id=task.correlation_id,
    )

    terminal = status.lower()
    if terminal == "running":
        now = timezone.now()
        task.status = NodeTask.Status.RUNNING
        if replace_result:
            merged = dict(result or {})
        else:
            merged = dict(task.result or {})
            if result:
                merged.update(result)
        task.result = merged
        if error:
            task.last_error = error[:2000]
        update_fields = ["status", "result", "last_error", "updated_at"]
        if _task_has_detached_marker(task):
            update_fields = list(
                dict.fromkeys(update_fields + _apply_detached_running_state(task=task, merged=merged, now=now))
            )
        task.save(update_fields=update_fields)
        _sync_task_info(task)
        redis_store.push_task_stream(
            task_id=str(task.id),
            message={
                "task_id": str(task.id),
                "status": task.status,
                "result": task.result,
                "error": task.last_error,
                "alive": True,
            },
        )
        return task
    if terminal in ("success", "succeeded", "ok"):
        task.status = NodeTask.Status.SUCCESS
    elif terminal in ("canceled", "cancelled"):
        task.status = NodeTask.Status.CANCELED
    else:
        task.status = NodeTask.Status.FAILED
        task.last_error = (error or terminal)[:2000]

    if result:
        task.result = result
    task.save(update_fields=["status", "result", "last_error", "updated_at"])
    _sync_task_info(task)
    redis_store.push_task_stream(
        task_id=str(task.id),
        message=_terminal_stream_message(task),
    )
    if task.status == NodeTask.Status.SUCCESS:
        logger.info("agent task completed %s status=%s", ctx, task.status)
    elif task.status == NodeTask.Status.CANCELED:
        logger.info("agent task canceled %s status=%s error=%s", ctx, task.status, task.last_error[:200])
    else:
        logger.warning(
            "agent task failed %s status=%s error=%s",
            ctx,
            task.status,
            (task.last_error or error or terminal)[:500],
        )
    return task


@transaction.atomic
def cancel_task(
    *,
    task_id: uuid.UUID | str,
    reason: str = "canceled",
) -> NodeTask | None:
    task = NodeTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None:
        return None
    if task.status not in _ACTIVE_STATUSES:
        return task

    task.last_error = reason[:2000]
    if task.status == NodeTask.Status.PENDING:
        task.status = NodeTask.Status.CANCELED
        task.save(update_fields=["status", "last_error", "updated_at"])
        _send_cancel_command(task=task)
        _sync_task_info(task)
        redis_store.push_task_stream(
            task_id=str(task.id),
            message=_terminal_stream_message(task),
        )
        return task

    merged = dict(task.result or {})
    merged["cancel_requested"] = True
    merged["cancel_requested_at"] = timezone.now().isoformat()
    task.result = merged
    task.save(update_fields=["result", "last_error", "updated_at"])
    _send_cancel_command(task=task)
    _sync_task_info(task)
    redis_store.push_task_stream(
        task_id=str(task.id),
        message={
            "task_id": str(task.id),
            "status": task.status,
            "result": task.result,
            "error": task.last_error,
            "cancel_requested": True,
            "alive": True,
        },
    )
    return task


def _send_cancel_command(*, task: NodeTask) -> None:
    from apps.node.ws.downlink import send_task_cancel

    try:
        send_task_cancel(task=task)
    except (RuntimeError, OSError) as exc:
        logger.warning("cancel send failed task=%s: %s", task.id, exc)


@transaction.atomic
def fail_active_tasks_for_node(*, node_id: int, reason: str) -> int:
    qs = NodeTask.objects.select_for_update().filter(
        node_id=node_id,
        status__in=_ACTIVE_STATUSES,
    )
    count = 0
    for task in qs:
        if _task_has_detached_marker(task):
            continue
        task.status = NodeTask.Status.FAILED
        task.last_error = reason[:2000]
        task.save(update_fields=["status", "last_error", "updated_at"])
        logger.warning(
            "agent task failed (node offline) %s error=%s",
            task_log_context(node_id=node_id, task_id=str(task.id), kind=task.kind),
            reason[:200],
        )
        redis_store.push_task_stream(
            task_id=str(task.id),
            message=_terminal_stream_message(task),
        )
        from apps.node.services.internal.task_offline_reconcile import sync_platform_tasks_for_node_task

        sync_platform_tasks_for_node_task(node_task=task)
        count += 1
    return count


def sweep_watchdog_timeouts(*, queryset: QuerySet[NodeTask] | None = None, limit: int = 500) -> int:
    now = timezone.now()
    qs = queryset
    if qs is None:
        qs = NodeTask.objects.filter(
            status__in=_ACTIVE_STATUSES,
            watchdog_deadline_at__lt=now,
        )
    ids = list(
        qs.order_by("watchdog_deadline_at", "pk").values_list("pk", flat=True)[: int(limit)]
    )

    marked = 0
    for pk in ids:
        with transaction.atomic():
            task = (
                NodeTask.objects.select_for_update()
                .filter(
                    pk=pk,
                    status__in=_ACTIVE_STATUSES,
                    watchdog_deadline_at__lt=timezone.now(),
                )
                .first()
            )
            if task is None:
                continue
            task.status = NodeTask.Status.TIMEOUT
            task.last_error = "watchdog timeout (no progress)"
            task.save(update_fields=["status", "last_error", "updated_at"])
            logger.warning(
                "agent task watchdog timeout %s",
                task_log_context(
                    node_id=task.node_id,
                    task_id=str(task.id),
                    kind=task.kind,
                ),
            )
            _send_cancel_command(task=task)
            _sync_task_info(task)
            redis_store.push_task_stream(
                task_id=str(task.id),
                message=_terminal_stream_message(task),
            )
            from apps.node.services.internal.task_offline_reconcile import sync_platform_tasks_for_node_task

            sync_platform_tasks_for_node_task(node_task=task)
            marked += 1
    return marked
