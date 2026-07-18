from __future__ import annotations

from apps.node.models import NodeTask
from apps.protection.models import BackupSourceSnapshot
from apps.protection.services.progress.backup_runtime import (
    sync_backup_task_progress,
)
from apps.restore.models import RestoreRecord, RestoreRecordItem
from apps.protection.services.progress.restore_runtime import (
    sync_restore_task_progress,
    update_restore_item_progress_snapshot,
)
from apps.task.models import Task

_RESTORE_CORRELATION = "restore.record"


def maybe_trigger_restore_progress(*, node_task: NodeTask) -> None:
    if node_task.correlation_type != _RESTORE_CORRELATION or not node_task.correlation_id:
        return
    record = RestoreRecord.objects.filter(
        organization_id=node_task.organization_id,
        task_uuid=node_task.correlation_id,
    ).first()
    if record is None:
        return
    item_id = _payload_int(node_task.payload, "restore_record_item_id")
    if not item_id:
        return
    item = RestoreRecordItem.objects.filter(
        organization_id=record.organization_id,
        restore_record=record,
        id=item_id,
    ).first()
    if item is None:
        return
    progress = _node_task_progress(node_task)
    if progress:
        update_restore_item_progress_snapshot(item=item, progress=progress, node_task=node_task)
    task = Task.objects.filter(
        organization_id=record.organization_id,
        task_uuid=record.task_uuid,
    ).first()
    if task is not None:
        sync_restore_task_progress(record=record, task=task)


def sync_restore_items_from_node_tasks(*, record: RestoreRecord) -> None:
    for item in record.items.order_by("id"):
        node_task = _node_task_for_restore_item(item=item, organization_id=record.organization_id)
        if node_task is None:
            continue
        progress = _node_task_progress(node_task)
        if progress:
            update_restore_item_progress_snapshot(item=item, progress=progress, node_task=node_task)


def sync_restore_record_progress(*, record: RestoreRecord) -> dict:
    sync_restore_items_from_node_tasks(record=record)
    task = Task.objects.filter(
        organization_id=record.organization_id,
        task_uuid=record.task_uuid,
    ).first()
    return sync_restore_task_progress(record=record, task=task)


def sync_backup_task_progress_from_snapshot(*, task: Task) -> dict:
    snapshot = BackupSourceSnapshot.objects.filter(
        organization_id=task.organization_id,
        task_uuid=task.task_uuid,
    ).first()
    return sync_backup_task_progress(task=task, source_snapshot=snapshot)


def _node_task_for_restore_item(*, item: RestoreRecordItem, organization_id: int) -> NodeTask | None:
    if item.node_task_id:
        return NodeTask.objects.filter(pk=item.node_task_id, organization_id=organization_id).first()
    return None


def _node_task_progress(node_task: NodeTask) -> dict | None:
    result = node_task.result if isinstance(node_task.result, dict) else {}
    progress = result.get("last_progress")
    return progress if isinstance(progress, dict) else None


def _payload_int(payload, key: str) -> int:
    if not isinstance(payload, dict):
        return 0
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0
