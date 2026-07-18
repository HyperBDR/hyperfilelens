from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.node.services.interface import run_agent_task_sync
from apps.protection.models import BackupSourceSnapshot, BackupSourceSnapshotDirectory
from apps.protection.services.backup_task import (
    _resolve_execution_target,
    _set_step_status,
)
from apps.protection.services.kopia_snapshot_delete import classify_kopia_snapshot_delete_results
from apps.protection.services.repository_compatibility import validate_backup_repository_compatible
from apps.storage.services.internal.repository_access import (
    repository_uses_bound_proxy,
    resolve_repository_reader,
)
from apps.task.models import Task, TaskEvent, TaskResource, TaskStep
from apps.task.services.interface import (
    append_task_step_event,
    complete_task,
    create_task,
    retry_task,
    start_task,
)

logger = logging.getLogger(__name__)

_DELETE_LOCK_TTL_SECONDS = 7200
_DELETE_RETRY_MINUTES = (1, 4, 16, 30, 60, 120)
_DELETE_TERMINAL = {
    Task.Status.SUCCESS,
    Task.Status.FAILED,
    Task.Status.CANCELLED,
    Task.Status.TIMEOUT,
}


def _delete_lock_key(*, organization_id: int, source_snapshot_id: int) -> str:
    return f"protection:snapshot-delete:{organization_id}:{source_snapshot_id}"


def _active_delete_task(*, organization_id: int, source_snapshot_id: int) -> Task | None:
    return (
        Task.objects.filter(
            organization_id=organization_id,
            task_type=Task.Type.SNAPSHOT_DELETE,
            resources__resource_type=TaskResource.Type.SNAPSHOT,
            resources__resource_id=source_snapshot_id,
        )
        .exclude(status__in=_DELETE_TERMINAL)
        .order_by("-created_at", "-id")
        .first()
    )


def _latest_delete_task(*, organization_id: int, source_snapshot_id: int) -> Task | None:
    return (
        Task.objects.filter(
            organization_id=organization_id,
            task_type=Task.Type.SNAPSHOT_DELETE,
            resources__resource_type=TaskResource.Type.SNAPSHOT,
            resources__resource_id=source_snapshot_id,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def snapshot_delete_retry_delay(retry_count: int) -> timedelta:
    index = min(max(0, int(retry_count)), len(_DELETE_RETRY_MINUTES) - 1)
    return timedelta(minutes=_DELETE_RETRY_MINUTES[index])


def _snapshot_delete_rows(source_snapshot: BackupSourceSnapshot) -> list[BackupSourceSnapshotDirectory]:
    return list(
        BackupSourceSnapshotDirectory.objects.filter(
            source_snapshot=source_snapshot,
        )
        .exclude(status=BackupSourceSnapshotDirectory.Status.DELETED)
        .order_by("id")
    )


def _kopia_snapshot_ids(rows: list[BackupSourceSnapshotDirectory]) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for row in rows:
        snapshot_id = str(row.kopia_snapshot_id or "").strip()
        if not snapshot_id or snapshot_id in seen:
            continue
        seen.add(snapshot_id)
        ids.append(snapshot_id)
    return ids


def _snapshot_directory_label(row: BackupSourceSnapshotDirectory) -> str:
    return str(row.source_path or row.display_name or row.backup_config_dir_id or "").strip()


def _kopia_snapshot_display(snapshot_id: str, directories: list[str]) -> str:
    clean_dirs = [item for item in directories if item]
    if not clean_dirs:
        return snapshot_id
    return f"{snapshot_id} ({', '.join(clean_dirs)})"


def _kopia_snapshot_directories_by_id(rows: list[BackupSourceSnapshotDirectory]) -> dict[str, list[str]]:
    directories_by_id: dict[str, list[str]] = {}
    for row in rows:
        snapshot_id = str(row.kopia_snapshot_id or "").strip()
        if not snapshot_id:
            continue
        directory = _snapshot_directory_label(row)
        if not directory:
            continue
        directories = directories_by_id.setdefault(snapshot_id, [])
        if directory not in directories:
            directories.append(directory)
    return directories_by_id


def create_snapshot_delete_task(
    *,
    source_snapshot: BackupSourceSnapshot,
    trigger_type: str = Task.TriggerType.SYSTEM,
) -> Task:
    if source_snapshot.status == BackupSourceSnapshot.Status.DELETED:
        raise ValidationError({"source_snapshot_id": "Snapshot is already deleted."})
    active = _active_delete_task(
        organization_id=source_snapshot.organization_id,
        source_snapshot_id=source_snapshot.id,
    )
    if active is not None:
        return active

    rows = _snapshot_delete_rows(source_snapshot)
    kopia_ids = _kopia_snapshot_ids(rows)
    payload = {
        "source_snapshot_id": source_snapshot.id,
        "backup_config_id": source_snapshot.backup_config_id,
        "repository_id": source_snapshot.repository_id,
        "kopia_snapshot_ids": kopia_ids,
        "directory_ids": [row.id for row in rows],
    }
    with transaction.atomic():
        task = create_task(
            organization_id=source_snapshot.organization_id,
            task_type=Task.Type.SNAPSHOT_DELETE,
            display_name=f"Delete snapshot {source_snapshot.snapshot_uid}",
            trigger_type=trigger_type,
            request_payload=payload,
            resources=[
                {
                    "resource_type": TaskResource.Type.BACKUP_SOURCE,
                    "resource_subtype": source_snapshot.source_type,
                    "resource_id": source_snapshot.source_ref_id,
                    "is_primary": True,
                },
                {
                    "resource_type": TaskResource.Type.REPOSITORY,
                    "resource_id": source_snapshot.repository_id,
                },
            ],
            steps=[
                {"step_name": "prepare_snapshot_delete"},
                {"step_name": "delete_kopia_snapshots"},
                {"step_name": "finalize_snapshot_delete"},
            ],
        )
        source_snapshot.status = BackupSourceSnapshot.Status.DELETING
        source_snapshot.save(update_fields=["status", "updated_at"])
    return task


def queue_snapshot_delete_task(*, task: Task, source_snapshot_id: int) -> None:
    from apps.protection.tasks.snapshot_delete import execute_snapshot_delete_task

    execute_snapshot_delete_task.delay(
        organization_id=task.organization_id,
        task_uuid=str(task.task_uuid),
        source_snapshot_id=int(source_snapshot_id),
    )


def create_and_queue_snapshot_delete_task(
    *,
    source_snapshot: BackupSourceSnapshot,
    trigger_type: str = Task.TriggerType.SYSTEM,
) -> Task:
    with transaction.atomic():
        locked_snapshot = BackupSourceSnapshot.objects.select_for_update().get(
            organization_id=source_snapshot.organization_id,
            id=source_snapshot.id,
        )
        active = _active_delete_task(
            organization_id=locked_snapshot.organization_id,
            source_snapshot_id=locked_snapshot.id,
        )
        if active is not None:
            return active
        if locked_snapshot.status == BackupSourceSnapshot.Status.DELETE_FAILED:
            task = _latest_delete_task(
                organization_id=locked_snapshot.organization_id,
                source_snapshot_id=locked_snapshot.id,
            )
            if task is not None and task.status in _DELETE_TERMINAL - {Task.Status.SUCCESS}:
                task = retry_task(
                    task_uuid=task.task_uuid,
                    organization_id=task.organization_id,
                    reason="Snapshot delete requested again",
                )
                locked_snapshot.status = BackupSourceSnapshot.Status.DELETING
                locked_snapshot.error_code = ""
                locked_snapshot.error_message = ""
                locked_snapshot.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            else:
                task = create_snapshot_delete_task(
                    source_snapshot=locked_snapshot,
                    trigger_type=trigger_type,
                )
        else:
            task = create_snapshot_delete_task(
                source_snapshot=locked_snapshot,
                trigger_type=trigger_type,
            )
        transaction.on_commit(
            lambda task_id=task.id, snapshot_id=locked_snapshot.id: queue_snapshot_delete_task(
                task=Task.objects.get(id=task_id),
                source_snapshot_id=snapshot_id,
            )
        )
    return task


def _complete_empty_delete(task: Task, source_snapshot: BackupSourceSnapshot) -> dict[str, Any]:
    now = timezone.now()
    BackupSourceSnapshotDirectory.objects.filter(source_snapshot=source_snapshot).exclude(
        status=BackupSourceSnapshotDirectory.Status.DELETED
    ).update(status=BackupSourceSnapshotDirectory.Status.DELETED, updated_at=now)
    source_snapshot.status = BackupSourceSnapshot.Status.DELETED
    source_snapshot.deleted_at = now
    source_snapshot.error_code = ""
    source_snapshot.error_message = ""
    source_snapshot.save(
        update_fields=["status", "deleted_at", "error_code", "error_message", "updated_at"]
    )
    result = {
        "source_snapshot_id": source_snapshot.id,
        "deleted_count": 0,
        "failed_count": 0,
        "results": [],
        "message": "Logical snapshot had no physical Kopia snapshots.",
    }
    complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=Task.Status.SUCCESS,
        progress=100,
        result_payload=result,
    )
    return result


def run_snapshot_delete_task(
    *,
    organization_id: int,
    task_uuid: str,
    source_snapshot_id: int,
) -> dict[str, Any]:
    lock_key = _delete_lock_key(
        organization_id=organization_id,
        source_snapshot_id=source_snapshot_id,
    )
    if not cache.add(lock_key, "running", timeout=_DELETE_LOCK_TTL_SECONDS):
        return {"task_uuid": str(task_uuid), "source_snapshot_id": source_snapshot_id, "status": "locked"}
    try:
        return _run_snapshot_delete_task_locked(
            organization_id=organization_id,
            task_uuid=task_uuid,
            source_snapshot_id=source_snapshot_id,
        )
    finally:
        cache.delete(lock_key)


def _run_snapshot_delete_task_locked(
    *,
    organization_id: int,
    task_uuid: str,
    source_snapshot_id: int,
) -> dict[str, Any]:
    task = Task.objects.filter(organization_id=organization_id, task_uuid=task_uuid).first()
    if task is None:
        raise Task.DoesNotExist
    source_snapshot = BackupSourceSnapshot.objects.filter(
        organization_id=organization_id,
        id=source_snapshot_id,
    ).first()
    if source_snapshot is None:
        raise BackupSourceSnapshot.DoesNotExist
    if task.status in _DELETE_TERMINAL:
        return task.result_payload if isinstance(task.result_payload, dict) else {}
    if task.status == Task.Status.PENDING:
        task = start_task(task_uuid=task.task_uuid, organization_id=organization_id)

    rows = _snapshot_delete_rows(source_snapshot)
    kopia_ids = _kopia_snapshot_ids(rows)
    kopia_directories_by_id = _kopia_snapshot_directories_by_id(rows)

    _set_step_status(
        task=task,
        step_name="prepare_snapshot_delete",
        status=TaskStep.Status.SUCCESS,
        progress=100,
        task_progress=10,
        current_step="delete_kopia_snapshots",
    )
    if not kopia_ids:
        _set_step_status(
            task=task,
            step_name="delete_kopia_snapshots",
            status=TaskStep.Status.SKIPPED,
            progress=100,
            task_progress=80,
        )
        _set_step_status(
            task=task,
            step_name="finalize_snapshot_delete",
            status=TaskStep.Status.SUCCESS,
            progress=100,
            task_progress=100,
        )
        return _complete_empty_delete(task, source_snapshot)

    repository = validate_backup_repository_compatible(
        organization_id=organization_id,
        source_type=source_snapshot.source_type,
        source_ref_id=source_snapshot.source_ref_id,
        repository_id=source_snapshot.repository_id,
    )
    fallback_target = None
    if not repository_uses_bound_proxy(repository):
        fallback_target = _resolve_execution_target(source_snapshot=source_snapshot)
    repository_access = resolve_repository_reader(
        repository=repository,
        fallback_node=fallback_target.node if fallback_target is not None else None,
        source_type=source_snapshot.source_type,
        source_ref_id=source_snapshot.source_ref_id,
    )
    _set_step_status(
        task=task,
        step_name="delete_kopia_snapshots",
        status=TaskStep.Status.RUNNING,
        progress=0,
        task_progress=10,
        current_step="delete_kopia_snapshots",
    )
    for snapshot_id in kopia_ids:
        directories = kopia_directories_by_id.get(snapshot_id, [])
        append_task_step_event(
            task=task,
            step_name="delete_kopia_snapshots",
            message="Deleting physical Kopia snapshot",
            metadata={
                "kopia_snapshot_id": snapshot_id,
                "kopia_snapshot_display": _kopia_snapshot_display(snapshot_id, directories),
                "source_path": directories[0] if directories else "",
                "paths": directories,
            },
        )
    outcome = run_agent_task_sync(
        organization_id=organization_id,
        node_id=repository_access.node.id,
        kind="snapshot.delete",
        payload={
            "repository": repository_access.repository_payload,
            "kopia_snapshot_ids": kopia_ids,
        },
        correlation_type="protection.snapshot_delete",
        correlation_id=str(task.task_uuid),
        wait_timeout_seconds=3600,
    )
    result = outcome.result if isinstance(outcome.result, dict) else {}
    item_results = result.get("results") if isinstance(result.get("results"), list) else []
    deleted_ids, already_absent_ids, hard_failures = classify_kopia_snapshot_delete_results(
        [item for item in item_results if isinstance(item, dict)],
    )
    reconciled_ids = deleted_ids | already_absent_ids
    hard_failed = bool(outcome.timed_out or hard_failures or (not outcome.ok and not reconciled_ids))
    now = timezone.now()
    if reconciled_ids:
        BackupSourceSnapshotDirectory.objects.filter(
            source_snapshot=source_snapshot,
            kopia_snapshot_id__in=list(reconciled_ids),
        ).update(status=BackupSourceSnapshotDirectory.Status.DELETED, updated_at=now)
    if not hard_failed:
        BackupSourceSnapshotDirectory.objects.filter(
            source_snapshot=source_snapshot,
            kopia_snapshot_id__isnull=True,
        ).exclude(status=BackupSourceSnapshotDirectory.Status.DELETED).update(
            status=BackupSourceSnapshotDirectory.Status.DELETED,
            updated_at=now,
        )
        BackupSourceSnapshotDirectory.objects.filter(
            source_snapshot=source_snapshot,
            kopia_snapshot_id="",
        ).exclude(status=BackupSourceSnapshotDirectory.Status.DELETED).update(
            status=BackupSourceSnapshotDirectory.Status.DELETED,
            updated_at=now,
        )
    deleted_count = BackupSourceSnapshotDirectory.objects.filter(
        source_snapshot=source_snapshot,
        status=BackupSourceSnapshotDirectory.Status.DELETED,
    ).count()
    remaining_count = BackupSourceSnapshotDirectory.objects.filter(
        source_snapshot=source_snapshot,
    ).exclude(status=BackupSourceSnapshotDirectory.Status.DELETED).count()
    hard_failed = hard_failed or remaining_count > 0
    task_result = {
        "source_snapshot_id": source_snapshot.id,
        "deleted_count": deleted_count,
        "failed_count": remaining_count if hard_failed else 0,
        "already_absent_count": len(already_absent_ids),
        "results": item_results,
    }
    if remaining_count == 0 and not hard_failed:
        source_snapshot.status = BackupSourceSnapshot.Status.DELETED
        source_snapshot.deleted_at = now
        source_snapshot.error_code = ""
        source_snapshot.error_message = ""
        source_snapshot.save(
            update_fields=["status", "deleted_at", "error_code", "error_message", "updated_at"]
        )
        _set_step_status(
            task=task,
            step_name="delete_kopia_snapshots",
            status=TaskStep.Status.SUCCESS,
            progress=100,
            task_progress=80,
        )
        _set_step_status(
            task=task,
            step_name="finalize_snapshot_delete",
            status=TaskStep.Status.SUCCESS,
            progress=100,
            task_progress=100,
            current_step="finalize_snapshot_delete",
        )
        complete_task(
            task_uuid=task.task_uuid,
            organization_id=organization_id,
            status=Task.Status.SUCCESS,
            progress=100,
            result_payload=task_result,
        )
        return task_result

    error_message = str(outcome.task.last_error or "One or more physical snapshots failed to delete.")[:2000]
    source_snapshot.status = BackupSourceSnapshot.Status.DELETE_FAILED
    source_snapshot.error_code = "SNAPSHOT_DELETE_FAILED"
    source_snapshot.error_message = error_message
    source_snapshot.save(update_fields=["status", "error_code", "error_message", "updated_at"])
    append_task_step_event(
        task=task,
        step_name="delete_kopia_snapshots",
        level=TaskEvent.Level.ERROR,
        message="Physical snapshot delete failed",
        metadata={"error_message": error_message, "results": item_results},
    )
    _set_step_status(
        task=task,
        step_name="delete_kopia_snapshots",
        status=TaskStep.Status.FAILED,
        progress=0,
        task_progress=10,
    )
    _set_step_status(
        task=task,
        step_name="finalize_snapshot_delete",
        status=TaskStep.Status.FAILED,
        progress=0,
        task_progress=10,
        current_step="finalize_snapshot_delete",
    )
    complete_task(
        task_uuid=task.task_uuid,
        organization_id=organization_id,
        status=Task.Status.FAILED,
        progress=10,
        result_payload=task_result,
        error_code="SNAPSHOT_DELETE_FAILED",
        error_message=error_message,
    )
    return task_result


def reconcile_snapshot_delete_tasks(*, now=None, limit: int = 100) -> dict[str, int]:
    current = now or timezone.now()
    requeued_pending = 0
    recovered_running = 0
    retried_failed = 0

    stale_pending = list(
        Task.objects.filter(
            task_type=Task.Type.SNAPSHOT_DELETE,
            status=Task.Status.PENDING,
            updated_at__lte=current - timedelta(minutes=5),
        ).order_by("updated_at", "id")[:limit]
    )
    for task in stale_pending:
        snapshot_id = int((task.request_payload or {}).get("source_snapshot_id") or 0)
        snapshot = BackupSourceSnapshot.objects.filter(
            organization_id=task.organization_id,
            id=snapshot_id,
            status=BackupSourceSnapshot.Status.DELETING,
        ).first()
        latest = _latest_delete_task(
            organization_id=task.organization_id,
            source_snapshot_id=snapshot_id,
        ) if snapshot_id else None
        if snapshot is not None and latest is not None and latest.id == task.id:
            Task.objects.filter(id=task.id, status=Task.Status.PENDING).update(updated_at=current)
            queue_snapshot_delete_task(task=task, source_snapshot_id=snapshot_id)
            requeued_pending += 1

    stale_running = list(
        Task.objects.filter(
            task_type=Task.Type.SNAPSHOT_DELETE,
            status=Task.Status.RUNNING,
            updated_at__lte=current - timedelta(hours=2),
        ).order_by("updated_at", "id")[:limit]
    )
    for task in stale_running:
        snapshot_id = int((task.request_payload or {}).get("source_snapshot_id") or 0)
        latest = _latest_delete_task(
            organization_id=task.organization_id,
            source_snapshot_id=snapshot_id,
        ) if snapshot_id else None
        if latest is None or latest.id != task.id:
            continue
        complete_task(
            task_uuid=task.task_uuid,
            organization_id=task.organization_id,
            status=Task.Status.FAILED,
            progress=float(task.progress),
            result_payload=task.result_payload if isinstance(task.result_payload, dict) else {},
            error_code="SNAPSHOT_DELETE_INTERRUPTED",
            error_message="Snapshot delete worker was interrupted before finalization.",
        )
        if snapshot_id:
            BackupSourceSnapshot.objects.filter(
                organization_id=task.organization_id,
                id=snapshot_id,
                status=BackupSourceSnapshot.Status.DELETING,
            ).update(
                status=BackupSourceSnapshot.Status.DELETE_FAILED,
                error_code="SNAPSHOT_DELETE_INTERRUPTED",
                error_message="Snapshot delete worker was interrupted before finalization.",
                updated_at=current,
            )
        recovered_running += 1

    failed_snapshots = list(
        BackupSourceSnapshot.objects.filter(status=BackupSourceSnapshot.Status.DELETE_FAILED)
        .order_by("updated_at", "id")[:limit]
    )
    for snapshot in failed_snapshots:
        with transaction.atomic():
            locked = BackupSourceSnapshot.objects.select_for_update().get(id=snapshot.id)
            if locked.status != BackupSourceSnapshot.Status.DELETE_FAILED:
                continue
            task = _latest_delete_task(
                organization_id=locked.organization_id,
                source_snapshot_id=locked.id,
            )
            if task is None or task.status not in _DELETE_TERMINAL - {Task.Status.SUCCESS}:
                continue
            due_from = task.finished_at or task.updated_at
            if due_from + snapshot_delete_retry_delay(task.retry_count) > current:
                continue
            task = retry_task(
                task_uuid=task.task_uuid,
                organization_id=task.organization_id,
                reason="Automatic snapshot delete retry",
            )
            locked.status = BackupSourceSnapshot.Status.DELETING
            locked.error_code = ""
            locked.error_message = ""
            locked.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            transaction.on_commit(
                lambda task_id=task.id, snapshot_id=locked.id: queue_snapshot_delete_task(
                    task=Task.objects.get(id=task_id),
                    source_snapshot_id=snapshot_id,
                )
            )
            retried_failed += 1

    return {
        "requeued_pending": requeued_pending,
        "recovered_running": recovered_running,
        "retried_failed": retried_failed,
    }
