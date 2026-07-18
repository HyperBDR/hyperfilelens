from __future__ import annotations

from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.node.models import NodeTask
from apps.restore.models import RestoreRecord, RestoreRecordItem
from apps.protection.services.progress.orchestrated_progress import RESTORE_FINALIZE_START
from apps.task.models import Task, TaskEvent, TaskStep
from apps.task.services.interface import append_task_step_event, complete_task, start_task

_TERMINAL_NODE_STATUSES = {
    NodeTask.Status.SUCCESS,
    NodeTask.Status.FAILED,
    NodeTask.Status.TIMEOUT,
    NodeTask.Status.CANCELED,
}


@receiver(post_save, sender=NodeTask)
def sync_restore_record_from_node_task(sender: type[NodeTask], instance: NodeTask, **kwargs: Any) -> None:
    if instance.correlation_type == "restore.repository_server" and instance.correlation_id:
        _handle_restore_repository_server_task(node_task=instance)
        return
    if instance.correlation_type != "restore.record" or not instance.correlation_id:
        return
    record = RestoreRecord.objects.filter(
        organization_id=instance.organization_id,
        task_uuid=instance.correlation_id,
    ).first()
    if record is None:
        return
    product_task = Task.objects.filter(
        organization_id=record.organization_id,
        task_uuid=record.task_uuid,
    ).first()
    if product_task is None:
        return
    if instance.status in {NodeTask.Status.PENDING, NodeTask.Status.RUNNING}:
        _ensure_product_task_running(product_task)
        from apps.restore.services.restore_progress import maybe_trigger_restore_progress

        maybe_trigger_restore_progress(node_task=instance)
        _set_step_status(
            task=product_task,
            step_name="restore",
            status=TaskStep.Status.RUNNING,
            current_step="restore",
        )
        return
    if instance.status not in _TERMINAL_NODE_STATUSES:
        return
    item_id = _payload_int(instance.payload, "restore_record_item_id")
    if item_id:
        _sync_restore_item(record=record, item_id=item_id, node_task=instance)
    from apps.restore.services.restore_progress import sync_restore_record_progress

    sync_restore_record_progress(record=record)
    _finalize_record_if_done(record=record, product_task=product_task)


def _handle_restore_repository_server_task(*, node_task: NodeTask) -> None:
    if node_task.status not in _TERMINAL_NODE_STATUSES:
        return
    if node_task.kind != "repository.server.start":
        return
    record = RestoreRecord.objects.filter(
        organization_id=node_task.organization_id,
        task_uuid=node_task.correlation_id,
    ).first()
    if record is None:
        return
    product_task = Task.objects.filter(
        organization_id=record.organization_id,
        task_uuid=record.task_uuid,
    ).first()
    if product_task is None:
        return
    if node_task.status == NodeTask.Status.SUCCESS:
        from apps.restore.services.interface import _dispatch_restore_items

        _dispatch_restore_items(
            organization_id=record.organization_id,
            record=record,
            task=product_task,
        )
        return
    message = str(node_task.last_error or "").strip()
    if not message and isinstance(node_task.result, dict):
        message = str(node_task.result.get("error") or "").strip()
    message = (message or "Restore repository server failed.")[:2000]
    RestoreRecordItem.objects.filter(
        organization_id=record.organization_id,
        restore_record=record,
        node_task_id__isnull=True,
        status__in=[RestoreRecordItem.Status.PENDING, RestoreRecordItem.Status.RUNNING],
    ).update(
        status=RestoreRecordItem.Status.FAILED,
        error_code="RESTORE_REPOSITORY_SERVER_FAILED",
        error_message=message,
    )
    append_task_step_event(
        task=product_task,
        step_name="dispatch_agent",
        level=TaskEvent.Level.ERROR,
        message="Restore repository server failed",
        metadata={"node_task_id": str(node_task.id), "error_message": message},
    )
    _finalize_record_if_done(record=record, product_task=product_task)


def _ensure_product_task_running(task: Task) -> None:
    if task.status == Task.Status.PENDING:
        start_task(task_uuid=task.task_uuid, organization_id=task.organization_id)


def _sync_restore_item(*, record: RestoreRecord, item_id: int, node_task: NodeTask) -> None:
    item = RestoreRecordItem.objects.filter(
        organization_id=record.organization_id,
        restore_record=record,
        id=item_id,
    ).first()
    if item is None:
        return
    if node_task.status == NodeTask.Status.SUCCESS:
        item.status = RestoreRecordItem.Status.SUCCESS
        item.result_payload = node_task.result or {}
        item.error_code = ""
        item.error_message = ""
    elif node_task.status == NodeTask.Status.CANCELED:
        item.status = RestoreRecordItem.Status.CANCELLED
        item.result_payload = node_task.result or {}
        item.error_code = "TASK_CANCELLED"
        item.error_message = (node_task.last_error or "Restore stopped.").strip()[:2000]
    else:
        item.status = RestoreRecordItem.Status.FAILED
        item.result_payload = node_task.result or {}
        item.error_code = "RESTORE_AGENT_FAILED"
        item.error_message = (node_task.last_error or node_task.status or "Restore agent task failed.")[:2000]
    item.save(
        update_fields=[
            "status",
            "result_payload",
            "error_code",
            "error_message",
            "updated_at",
        ]
    )


def _finalize_record_if_done(*, record: RestoreRecord, product_task: Task) -> None:
    if product_task.status == Task.Status.CANCELLED:
        return
    statuses = list(record.items.values_list("status", flat=True))
    if not statuses or any(status in {RestoreRecordItem.Status.PENDING, RestoreRecordItem.Status.RUNNING} for status in statuses):
        return
    from apps.restore.services.interface import stop_restore_repository_servers

    stop_restore_repository_servers(task=product_task)
    failed = [
        status
        for status in statuses
        if status not in {RestoreRecordItem.Status.SUCCESS, RestoreRecordItem.Status.CANCELLED}
    ]
    result_payload = {
        "restore_record_id": record.id,
        "item_count": len(statuses),
        "failed_item_count": len(failed),
    }
    if failed:
        error_message = _record_error_message(record)
        _set_step_status(
            task=product_task,
            step_name="restore",
            status=TaskStep.Status.FAILED,
            progress=100,
            task_progress=RESTORE_FINALIZE_START,
            current_step="restore",
        )
        _set_step_status(
            task=product_task,
            step_name="finalize",
            status=TaskStep.Status.FAILED,
            progress=100,
            task_progress=RESTORE_FINALIZE_START,
            current_step="finalize",
        )
        append_task_step_event(
            task=product_task,
            step_name="finalize",
            level=TaskEvent.Level.ERROR,
            message="Restore finished with failed items",
            metadata={**result_payload, "error_message": error_message},
        )
        complete_task(
            task_uuid=product_task.task_uuid,
            organization_id=product_task.organization_id,
            status=Task.Status.FAILED,
            progress=RESTORE_FINALIZE_START,
            result_payload=result_payload,
            error_code="RESTORE_FAILED",
            error_message=error_message,
        )
        return
    _set_step_status(
        task=product_task,
        step_name="restore",
        status=TaskStep.Status.SUCCESS,
        progress=100,
        task_progress=RESTORE_FINALIZE_START,
        current_step="finalize",
    )
    _set_step_status(
        task=product_task,
        step_name="finalize",
        status=TaskStep.Status.SUCCESS,
        progress=100,
        task_progress=100,
        current_step="finalize",
    )
    append_task_step_event(
        task=product_task,
        step_name="finalize",
        message="Restore finished successfully",
        metadata=result_payload,
    )
    complete_task(
        task_uuid=product_task.task_uuid,
        organization_id=product_task.organization_id,
        status=Task.Status.SUCCESS,
        progress=100,
        result_payload=result_payload,
    )


def _payload_int(payload: Any, key: str) -> int:
    if not isinstance(payload, dict):
        return 0
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _record_error_message(record: RestoreRecord) -> str:
    item = record.items.exclude(error_message="").first()
    if item is not None:
        return item.error_message[:2000]
    return "One or more restore items failed."


def _set_step_status(
    *,
    task: Task,
    step_name: str,
    status: str,
    progress: int | float | None = None,
    task_progress: int | float | None = None,
    current_step: str | None = None,
) -> None:
    step = TaskStep.objects.filter(task=task, step_name=step_name).first()
    if step is not None:
        update_fields = ["status"]
        step.status = status
        if progress is not None:
            step.progress = progress
            update_fields.append("progress")
        step.save(update_fields=update_fields)
    task_updates: list[str] = []
    if current_step is not None:
        task.current_step = current_step
        task_updates.append("current_step")
    if task_progress is not None:
        task.progress = task_progress
        task_updates.append("progress")
    if task_updates:
        task_updates.append("updated_at")
        task.save(update_fields=task_updates)
