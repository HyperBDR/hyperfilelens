"""Idempotent projection repair for restore NodeTasks after worker handoff."""

from __future__ import annotations

from django.db.models import CharField, Exists, OuterRef, Subquery
from django.db.models.functions import Cast

from apps.node.models import NodeTask
from apps.restore.models import RestoreRecord, RestoreRecordItem
from apps.restore.signals import sync_restore_record_from_node_task
from apps.task.models import Task
from apps.task.services.interface import TERMINAL_STATUSES


_RESTORE_CORRELATIONS = ("restore.record", "restore.repository_server")
_TERMINAL_NODE_STATUSES = (
    NodeTask.Status.SUCCESS,
    NodeTask.Status.FAILED,
    NodeTask.Status.TIMEOUT,
    NodeTask.Status.CANCELED,
)
_ACTIVE_ITEM_STATUSES = (
    RestoreRecordItem.Status.PENDING,
    RestoreRecordItem.Status.RUNNING,
)


def reconcile_restore_node_task_projections(*, limit: int = 200) -> dict[str, int]:
    """Repair item projections and nonterminal product tasks without starvation."""
    candidates = _candidate_terminal_node_tasks(limit=max(1, int(limit)))
    replayed = 0
    for node_task in candidates:
        if not _projection_needs_replay(node_task=node_task):
            continue
        sync_restore_record_from_node_task(NodeTask, node_task)
        replayed += 1
    return {"candidates": len(candidates), "replayed": replayed}


def _candidate_terminal_node_tasks(*, limit: int) -> list[NodeTask]:
    """Select work from incomplete projections instead of a moving task window."""
    node_task_ids = (
        RestoreRecordItem.objects.filter(
            node_task_id__isnull=False,
            terminal_projection_at__isnull=True,
        )
        .order_by()
        .values("node_task_id")
    )
    candidates = list(
        NodeTask.objects.filter(
            id__in=Subquery(node_task_ids),
            correlation_type="restore.record",
            status__in=_TERMINAL_NODE_STATUSES,
        ).order_by("updated_at", "id")[:limit]
    )

    remaining = max(0, limit - len(candidates))
    if remaining == 0:
        return candidates

    active_task_uuids = (
        Task.objects.filter(
            task_type=Task.Type.RESTORE,
            status__in=(Task.Status.PENDING, Task.Status.RUNNING),
        )
        .order_by()
        .values("task_uuid")
    )
    active_items = RestoreRecordItem.objects.filter(
        restore_record_id=OuterRef("pk"),
        status__in=_ACTIVE_ITEM_STATUSES,
    )
    terminal_node_task = (
        NodeTask.objects.filter(
            correlation_type__in=_RESTORE_CORRELATIONS,
            correlation_id=Cast(OuterRef("task_uuid"), output_field=CharField()),
            status__in=_TERMINAL_NODE_STATUSES,
        )
        .order_by("-updated_at", "-id")
        .values("id")[:1]
    )
    terminal_node_task_ids = (
        RestoreRecord.objects.filter(task_uuid__in=Subquery(active_task_uuids))
        .annotate(has_active_items=Exists(active_items))
        .filter(has_active_items=False)
        .annotate(terminal_node_task_id=Subquery(terminal_node_task))
        .filter(terminal_node_task_id__isnull=False)
        .order_by("updated_at", "id")
        .values("terminal_node_task_id")[:remaining]
    )
    seen = {node_task.id for node_task in candidates}
    additional = NodeTask.objects.filter(
        id__in=Subquery(terminal_node_task_ids),
    ).order_by("updated_at", "id")
    for node_task in additional:
        if node_task.id in seen:
            continue
        candidates.append(node_task)
        seen.add(node_task.id)
    return candidates


def _projection_needs_replay(*, node_task: NodeTask) -> bool:
    if node_task.correlation_type == "restore.record":
        payload = node_task.payload if isinstance(node_task.payload, dict) else {}
        try:
            item_id = int(payload.get("restore_record_item_id"))
        except (TypeError, ValueError):
            return False
        item = RestoreRecordItem.objects.select_related("restore_record").filter(
            id=item_id,
            node_task_id=node_task.id,
        ).first()
        if item is None:
            return False
        task = Task.objects.filter(
            organization_id=item.restore_record.organization_id,
            task_uuid=item.restore_record.task_uuid,
        ).first()
        if task is None:
            return False
        if item.terminal_projection_at is None:
            return True
        if task.status in TERMINAL_STATUSES:
            return False
        return not RestoreRecordItem.objects.filter(
            restore_record=item.restore_record,
            status__in=_ACTIVE_ITEM_STATUSES,
        ).exists()

    record = RestoreRecord.objects.filter(
        task_uuid=node_task.correlation_id,
    ).first()
    if record is None:
        return False
    task = Task.objects.filter(
        organization_id=record.organization_id,
        task_uuid=record.task_uuid,
    ).first()
    if task is None or task.status in TERMINAL_STATUSES:
        return False
    return not RestoreRecordItem.objects.filter(
        restore_record=record,
        status__in=_ACTIVE_ITEM_STATUSES,
    ).exists()
