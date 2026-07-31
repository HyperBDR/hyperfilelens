from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from apps.restore.models import RestoreRecord, RestoreRecordItem
from apps.task.models import Task, TaskEvent
from apps.task.services.interface import append_task_step_event

RESTORE_EVENT_SCHEMA_KEY = "restore_event_schema_version"
RESTORE_EVENT_SCHEMA_VERSION = 1

_RESTORE_STEP_NAME = "restore"
_RESTORE_EXECUTION_STARTED = "Restore execution started"
_TERMINAL_ITEM_STATUSES = {
    RestoreRecordItem.Status.SUCCESS,
    RestoreRecordItem.Status.FAILED,
    RestoreRecordItem.Status.SKIPPED,
    RestoreRecordItem.Status.CANCELLED,
}


def restore_step_events_enabled(*, task: Task) -> bool:
    payload = task.request_payload if isinstance(task.request_payload, dict) else {}
    return payload.get(RESTORE_EVENT_SCHEMA_KEY) == RESTORE_EVENT_SCHEMA_VERSION


def append_restore_execution_started_event(
    *,
    task: Task,
    record: RestoreRecord,
    items: Sequence[RestoreRecordItem],
) -> TaskEvent | None:
    if not restore_step_events_enabled(task=task):
        return None
    if TaskEvent.objects.filter(
        task=task,
        step__step_name=_RESTORE_STEP_NAME,
        message=_RESTORE_EXECUTION_STARTED,
    ).exists():
        return None
    source_paths = list(
        dict.fromkeys(
            path
            for item in items
            if (path := str(item.source_path or "").strip())
        )
    )
    metadata: dict[str, object] = {
        "restore_record_id": record.id,
        "item_count": len(items),
    }
    if source_paths:
        metadata["object_names"] = source_paths
    return append_task_step_event(
        task=task,
        step_name=_RESTORE_STEP_NAME,
        message=_RESTORE_EXECUTION_STARTED,
        metadata=metadata,
    )


def append_restore_item_terminal_event(
    *,
    task: Task,
    item: RestoreRecordItem,
    node_task_id: UUID | str | None,
    previous_status: str,
) -> TaskEvent | None:
    if not restore_step_events_enabled(task=task):
        return None
    if previous_status in _TERMINAL_ITEM_STATUSES or item.status not in _TERMINAL_ITEM_STATUSES:
        return None

    if item.status == RestoreRecordItem.Status.SUCCESS:
        message = "Restore item completed"
        level = TaskEvent.Level.INFO
    elif item.status == RestoreRecordItem.Status.CANCELLED:
        message = "Restore item cancelled"
        level = TaskEvent.Level.WARN
    else:
        message = "Restore item failed"
        level = TaskEvent.Level.ERROR

    metadata: dict[str, object] = {
        "restore_record_item_id": item.id,
        "kopia_snapshot_id": item.kopia_snapshot_id,
        "source_path": item.source_path,
        "target_path": item.target_path,
        "object_id": item.kopia_snapshot_id,
        "object_name": item.source_path,
    }
    if node_task_id:
        metadata["node_task_id"] = str(node_task_id)
    if item.error_code:
        metadata["error_code"] = item.error_code
    if item.error_message:
        metadata["error_message"] = item.error_message
    return append_task_step_event(
        task=task,
        step_name=_RESTORE_STEP_NAME,
        level=level,
        message=message,
        metadata=metadata,
    )
