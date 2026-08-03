"""Project Proxy and Data Gateway removals into the unified Operations task list."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.node import conf as node_conf
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.task.models import Task, TaskResource, TaskStep
from apps.task.signals import task_updated
from apps.task.services.interface import (
    append_task_step_event,
    complete_task,
    create_task,
    start_task,
)


_REMOVE_STEPS = (
    "prepare_node_remove",
    "dispatch_agent_uninstall",
    "cleanup_node_endpoint",
    "finalize_node_remove",
)
_TERMINAL_TASK_STATUSES = {
    Task.Status.SUCCESS,
    Task.Status.FAILED,
    Task.Status.CANCELLED,
    Task.Status.TIMEOUT,
}
_TERMINAL_NODE_TASK_STATUSES = {
    NodeTask.Status.SUCCESS,
    NodeTask.Status.FAILED,
    NodeTask.Status.CANCELED,
    NodeTask.Status.TIMEOUT,
}


def _is_direct_console_remove(node_task: NodeTask) -> bool:
    payload = node_task.payload if isinstance(node_task.payload, dict) else {}
    return (
        node_task.correlation_type == node_conf.LIFECYCLE_CORRELATION_TYPE
        and node_task.kind == "agent.uninstall"
        and node_task.node.role in {NodeRole.PROXY, NodeRole.GATEWAY}
        and not payload.get("source_unregister_task_id")
    )


def _node_snapshot(node: Node) -> dict[str, Any]:
    return {
        "id": int(node.id),
        "name": str(node.name or node.id),
        "role": str(node.role or ""),
        "endpoint": str(node.ip_address or ""),
        "registered_at": node.created_at.isoformat() if node.created_at else None,
    }


def _display_name(node: Node) -> str:
    kind = "Data Gateway" if node.role == NodeRole.GATEWAY else "Proxy Host"
    return f'Delete {kind} "{node.name or node.id}"'


def _operation_task(*, node_task: NodeTask) -> Task:
    existing = Task.objects.select_for_update().filter(
        organization_id=node_task.organization_id,
        task_type=Task.Type.NODE_LIFECYCLE,
        request_payload__node_task_id=str(node_task.id),
    ).first()
    if existing is not None:
        return existing
    return create_task(
        organization_id=node_task.organization_id,
        task_type=Task.Type.NODE_LIFECYCLE,
        display_name=_display_name(node_task.node),
        trigger_type=Task.TriggerType.MANUAL,
        request_payload={
            "operation": "remove",
            "node_task_id": str(node_task.id),
            "force": bool((node_task.payload or {}).get("force_cleanup")),
            "node": _node_snapshot(node_task.node),
        },
        resources=[
            {
                "resource_type": TaskResource.Type.HOST,
                "resource_subtype": str(node_task.node.role or ""),
                "resource_id": int(node_task.node_id),
                "is_primary": True,
            }
        ],
        steps=list(_REMOVE_STEPS),
    )


def _set_step(task: Task, step_name: str, status: str, progress: int) -> None:
    TaskStep.objects.filter(task=task, step_name=step_name).update(
        status=status,
        progress=Decimal("100.00")
        if status in {TaskStep.Status.SUCCESS, TaskStep.Status.WARNING}
        else Decimal(str(progress)),
    )
    task.current_step = step_name
    task.progress = Decimal(str(progress))
    task.save(update_fields=["current_step", "progress", "updated_at"])


def _result_payload(node_task: NodeTask) -> dict[str, Any]:
    result = dict(node_task.result or {})
    cleanup_complete = bool(
        result.get("cleanup_complete", node_task.status == NodeTask.Status.SUCCESS)
    )
    partial = node_task.status == NodeTask.Status.SUCCESS and not cleanup_complete
    return {
        **result,
        "node_task_id": str(node_task.id),
        "node_id": int(node_task.node_id),
        "node": _node_snapshot(node_task.node),
        "force": bool((node_task.payload or {}).get("force_cleanup")),
        "cleanup_complete": cleanup_complete,
        "cleanup_failures": [
            dict(item)
            for item in result.get("cleanup_failures") or []
            if isinstance(item, dict)
        ],
        "retained_resources": list(
            dict.fromkeys(
                str(item)
                for item in result.get("retained_resources") or []
                if str(item).strip()
            )
        ),
        "result": "partial_success"
        if partial
        else "success"
        if node_task.status == NodeTask.Status.SUCCESS
        else "failed",
    }


def _reconcile_active_task(*, task: Task, status: str) -> None:
    """Repair a projection changed independently of its authoritative NodeTask."""
    if task.status == status:
        return
    now = timezone.now()
    task.status = status
    task.result_payload = None
    task.error_code = None
    task.error_message = None
    task.finished_at = None
    if status == Task.Status.PENDING:
        task.started_at = None
        task.progress = Decimal("0.00")
        first_step = task.steps.order_by("step_index", "id").first()
        task.current_step = first_step.step_name if first_step else None
        task.steps.update(status=TaskStep.Status.PENDING, progress=Decimal("0.00"))
    else:
        task.started_at = task.started_at or now
    task.save(
        update_fields=[
            "status",
            "progress",
            "current_step",
            "result_payload",
            "error_code",
            "error_message",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )
    append_task_step_event(
        task=task,
        step_name=task.current_step,
        level="WARN",
        message=f"Node removal projection reconciled to {status}",
        metadata={"authoritative_status": status},
    )
    task_updated.send(
        sender=Task,
        task_uuid=str(task.task_uuid),
        organization_id=task.organization_id,
        status=task.status,
        progress=float(task.progress),
    )


def _reconcile_terminal_task(
    *,
    task: Task,
    status: str,
    progress: int,
    result_payload: dict[str, Any],
    error_code: str,
    error_message: str,
) -> Task:
    """Refresh a terminal projection without replaying terminal side effects."""
    desired_progress = Decimal(str(progress))
    desired_error_code = error_code or None
    desired_error_message = error_message or None
    changed = any(
        (
            task.status != status,
            task.progress != desired_progress,
            task.result_payload != result_payload,
            task.error_code != desired_error_code,
            task.error_message != desired_error_message,
        )
    )
    if not changed:
        return task
    task.status = status
    task.progress = desired_progress
    task.result_payload = result_payload
    task.error_code = desired_error_code
    task.error_message = desired_error_message
    task.finished_at = timezone.now()
    task.started_at = task.started_at or task.finished_at
    task.save(
        update_fields=[
            "status",
            "progress",
            "result_payload",
            "error_code",
            "error_message",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )
    append_task_step_event(
        task=task,
        step_name=task.current_step,
        level="INFO" if status == Task.Status.SUCCESS else "WARN",
        message="Node removal result reconciled from the authoritative Agent task",
        metadata={"authoritative_status": status},
    )
    task_updated.send(
        sender=Task,
        task_uuid=str(task.task_uuid),
        organization_id=task.organization_id,
        status=task.status,
        progress=float(task.progress),
    )
    return task


@transaction.atomic
def sync_node_remove_operation_task(*, node_task: NodeTask) -> Task | None:
    node_task = (
        NodeTask.objects.select_for_update()
        .select_related("node")
        .filter(pk=node_task.pk)
        .first()
    )
    if node_task is None or not _is_direct_console_remove(node_task):
        return None
    task = _operation_task(node_task=node_task)
    if node_task.status == NodeTask.Status.PENDING:
        if task.status in _TERMINAL_TASK_STATUSES:
            _reconcile_active_task(task=task, status=Task.Status.PENDING)
        return task
    task_was_terminal = task.status in _TERMINAL_TASK_STATUSES
    if task.status == Task.Status.PENDING:
        start_task(task_uuid=task.task_uuid, organization_id=task.organization_id)
        task.refresh_from_db()
    elif task_was_terminal and node_task.status == NodeTask.Status.RUNNING:
        _reconcile_active_task(task=task, status=Task.Status.RUNNING)
    _set_step(task, "prepare_node_remove", TaskStep.Status.SUCCESS, 15)
    dispatched = bool(node_task.dispatched_at or node_task.accepted_at)
    if not dispatched and node_task.status in _TERMINAL_NODE_TASK_STATUSES:
        dispatch_status = (
            TaskStep.Status.SKIPPED
            if node_task.status == NodeTask.Status.CANCELED
            else TaskStep.Status.FAILED
        )
        _set_step(task, "dispatch_agent_uninstall", dispatch_status, 35)
    else:
        _set_step(task, "dispatch_agent_uninstall", TaskStep.Status.SUCCESS, 35)
    if node_task.status == NodeTask.Status.RUNNING:
        _set_step(task, "cleanup_node_endpoint", TaskStep.Status.RUNNING, 65)
        return task

    result_payload = _result_payload(node_task)
    cleanup_complete = bool(result_payload["cleanup_complete"])
    node_succeeded = node_task.status == NodeTask.Status.SUCCESS
    if not dispatched or node_task.status == NodeTask.Status.CANCELED:
        _set_step(task, "cleanup_node_endpoint", TaskStep.Status.SKIPPED, 35)
    else:
        _set_step(
            task,
            "cleanup_node_endpoint",
            (
                TaskStep.Status.SUCCESS
                if cleanup_complete
                else TaskStep.Status.WARNING
                if node_succeeded
                else TaskStep.Status.FAILED
            ),
            85,
        )
    terminal_progress = 100 if node_succeeded else 85 if dispatched else 35
    _set_step(
        task,
        "finalize_node_remove",
        TaskStep.Status.SUCCESS if node_succeeded else TaskStep.Status.SKIPPED,
        terminal_progress,
    )
    terminal_status = (
        Task.Status.SUCCESS
        if node_succeeded
        else Task.Status.CANCELLED
        if node_task.status == NodeTask.Status.CANCELED
        else Task.Status.TIMEOUT
        if node_task.status == NodeTask.Status.TIMEOUT
        else Task.Status.FAILED
    )
    error_code = "" if node_succeeded else "NODE_REMOVE_FAILED"
    error_message = (
        "" if node_succeeded else str(node_task.last_error or "Node removal failed.")
    )
    if task_was_terminal:
        return _reconcile_terminal_task(
            task=task,
            status=terminal_status,
            progress=terminal_progress,
            result_payload=result_payload,
            error_code=error_code,
            error_message=error_message,
        )
    event_step = "cleanup_node_endpoint" if dispatched else "dispatch_agent_uninstall"
    append_task_step_event(
        task=task,
        step_name=event_step,
        level="WARN"
        if node_succeeded and not cleanup_complete
        else "INFO"
        if node_succeeded
        else "ERROR",
        message=(
            "Node removal completed with retained physical resources"
            if node_succeeded and not cleanup_complete
            else "Node removal completed"
            if node_succeeded
            else "Agent uninstall dispatch failed"
            if not dispatched
            else "Node removal failed"
        ),
        metadata={
            "dispatched": dispatched,
            "cleanup_complete": cleanup_complete,
            "cleanup_failures": result_payload["cleanup_failures"],
            "retained_resources": result_payload["retained_resources"],
        },
    )
    return complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=terminal_status,
        progress=terminal_progress,
        result_payload=result_payload,
        error_code=error_code,
        error_message=error_message,
    )


@transaction.atomic
def record_immediate_node_remove_task(
    *,
    node: Node,
    force: bool,
    result: dict[str, Any],
) -> Task | None:
    if node.role not in {NodeRole.PROXY, NodeRole.GATEWAY}:
        return None
    operation_id = str(result.get("operation_id") or f"force-remove:{node.id}")
    existing = Task.objects.filter(
        organization_id=node.organization_id,
        task_type=Task.Type.NODE_LIFECYCLE,
        request_payload__operation_id=operation_id,
    ).first()
    if existing is not None:
        return existing
    task = create_task(
        organization_id=node.organization_id,
        task_type=Task.Type.NODE_LIFECYCLE,
        display_name=_display_name(node),
        trigger_type=Task.TriggerType.MANUAL,
        request_payload={
            "operation": "remove",
            "operation_id": operation_id,
            "force": bool(force),
            "node": _node_snapshot(node),
        },
        resources=[
            {
                "resource_type": TaskResource.Type.HOST,
                "resource_subtype": str(node.role or ""),
                "resource_id": int(node.id),
                "is_primary": True,
            }
        ],
        steps=list(_REMOVE_STEPS),
    )
    start_task(task_uuid=task.task_uuid, organization_id=task.organization_id)
    task.refresh_from_db()
    _set_step(task, "prepare_node_remove", TaskStep.Status.SUCCESS, 20)
    _set_step(task, "dispatch_agent_uninstall", TaskStep.Status.SKIPPED, 40)
    _set_step(task, "cleanup_node_endpoint", TaskStep.Status.WARNING, 85)
    _set_step(task, "finalize_node_remove", TaskStep.Status.SUCCESS, 100)
    payload = {
        **result,
        "node": _node_snapshot(node),
        "result": "partial_success",
        "cleanup_complete": False,
    }
    return complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=Task.Status.SUCCESS,
        progress=100,
        result_payload=payload,
    )


__all__ = ["record_immediate_node_remove_task", "sync_node_remove_operation_task"]
