from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.storage.repositories.models import (
    Repository,
    RepositoryExecutionTarget,
    RepositoryMaintenanceState,
    RepositoryTask,
    RepositoryUsageShard,
)
from apps.task.models import Task, TaskResource, TaskStep
from apps.task.services.interface import append_task_event, complete_task, create_task, start_task


@dataclass(frozen=True)
class MaintenanceSettings:
    enabled: bool
    quick_interval: timedelta
    full_interval: timedelta
    scan_interval: timedelta
    window_start: time
    window_end: time
    timezone: ZoneInfo
    global_concurrency: int
    per_node_concurrency: int
    execution_timeout_seconds: int


def maintenance_settings() -> MaintenanceSettings:
    def positive_int(name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            value = int(raw)
        except ValueError as exc:
            raise ImproperlyConfigured(f"{name} must be an integer") from exc
        if value < 1:
            raise ImproperlyConfigured(f"{name} must be at least 1")
        return value

    def clock(name: str, default: str) -> time:
        raw = os.getenv(name, default).strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", raw):
            raise ImproperlyConfigured(f"{name} must use HH:MM format")
        try:
            return time.fromisoformat(raw)
        except ValueError as exc:
            raise ImproperlyConfigured(f"{name} must use HH:MM format") from exc

    timezone_name = os.getenv("STORAGE_MAINTENANCE_TIMEZONE", "UTC").strip() or "UTC"
    try:
        configured_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ImproperlyConfigured("STORAGE_MAINTENANCE_TIMEZONE must be an IANA timezone") from exc
    enabled_raw = os.getenv("STORAGE_MAINTENANCE_ENABLED", "true").strip().lower()
    if enabled_raw not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        raise ImproperlyConfigured("STORAGE_MAINTENANCE_ENABLED must be a boolean")
    enabled = enabled_raw in {"1", "true", "yes", "on"}
    window_start = clock("STORAGE_MAINTENANCE_FULL_WINDOW_START", "00:00")
    window_end = clock("STORAGE_MAINTENANCE_FULL_WINDOW_END", "06:00")
    if window_start == window_end:
        raise ImproperlyConfigured("Maintenance full window start and end must differ")
    return MaintenanceSettings(
        enabled=enabled,
        quick_interval=timedelta(seconds=positive_int("STORAGE_MAINTENANCE_QUICK_INTERVAL_SECONDS", 3600)),
        full_interval=timedelta(seconds=positive_int("STORAGE_MAINTENANCE_FULL_INTERVAL_SECONDS", 86400)),
        scan_interval=timedelta(seconds=positive_int("STORAGE_MAINTENANCE_SCAN_INTERVAL_SECONDS", 60)),
        window_start=window_start,
        window_end=window_end,
        timezone=configured_timezone,
        global_concurrency=positive_int("STORAGE_MAINTENANCE_GLOBAL_CONCURRENCY", 4),
        per_node_concurrency=positive_int("STORAGE_MAINTENANCE_PER_NODE_CONCURRENCY", 1),
        execution_timeout_seconds=positive_int("STORAGE_MAINTENANCE_EXECUTION_TIMEOUT_SECONDS", 21600),
    )


def _owner_identity(node_id: int | None) -> str:
    return f"hfl-maintenance@node-{node_id}" if node_id else "hfl-maintenance@controller"


def discover_repository_execution_targets(*, now: datetime | None = None) -> int:
    current = now or timezone.now()
    seen: set[str] = set()
    count = 0
    repositories = Repository.objects.filter(status=Repository.Status.CREATED).order_by("id")
    for repository in repositories:
        definitions: list[tuple[str, str, int | None, str]] = []
        if repository.repo_type == Repository.Type.S3:
            definitions.append((f"repository:{repository.id}", RepositoryExecutionTarget.OwnerType.CONTROLLER, None, ""))
        elif repository.repo_type in {Repository.Type.NAS, Repository.Type.PROXY_FS} and repository.bind_node_id:
            definitions.append((f"repository:{repository.id}", RepositoryExecutionTarget.OwnerType.NODE, int(repository.bind_node_id), ""))
        elif repository.repo_type == Repository.Type.NAS:
            shards = RepositoryUsageShard.objects.filter(
                organization_id=repository.organization_id,
                repository_id=repository.id,
                usage_scope=RepositoryUsageShard.Scope.DIRECT_NAS_AGENT,
                is_active=True,
            )
            for shard in shards:
                key = f"repository:{repository.id}:node:{shard.node_id}:subdir:{shard.repository_subdir}"
                definitions.append((key, RepositoryExecutionTarget.OwnerType.NODE, int(shard.node_id), shard.repository_subdir))
        for key, owner_type, node_id, subdir in definitions:
            seen.add(key)
            target, _created = RepositoryExecutionTarget.objects.update_or_create(
                target_key=key,
                defaults={
                    "organization_id": repository.organization_id,
                    "repository": repository,
                    "owner_type": owner_type,
                    "owner_node_id": node_id,
                    "owner_identity": _owner_identity(node_id),
                    "repository_subdir": subdir,
                    "is_active": True,
                },
            )
            RepositoryMaintenanceState.objects.get_or_create(
                execution_target=target,
                defaults={"next_quick_due_at": current, "next_full_due_at": current},
            )
            count += 1
    RepositoryExecutionTarget.objects.filter(is_active=True).exclude(target_key__in=seen).update(is_active=False)
    return count


def _inside_full_window(now: datetime, settings: MaintenanceSettings) -> bool:
    local_time = now.astimezone(settings.timezone).time().replace(tzinfo=None)
    if settings.window_start < settings.window_end:
        return settings.window_start <= local_time < settings.window_end
    return local_time >= settings.window_start or local_time < settings.window_end


def _stable_full_delay(target_key: str, settings: MaintenanceSettings) -> timedelta:
    start_seconds = settings.window_start.hour * 3600 + settings.window_start.minute * 60
    end_seconds = settings.window_end.hour * 3600 + settings.window_end.minute * 60
    width = (end_seconds - start_seconds) % 86400
    if width <= 1:
        return timedelta(0)
    digest = hashlib.sha256(target_key.encode("utf-8")).digest()
    return timedelta(seconds=int.from_bytes(digest[:8], "big") % width)


def _concurrency_available(target: RepositoryExecutionTarget, settings: MaintenanceSettings) -> bool:
    active = RepositoryExecutionTarget.objects.filter(active_task__status__in=[Task.Status.PENDING, Task.Status.RUNNING])
    if active.count() >= settings.global_concurrency:
        return False
    if target.owner_node_id and active.filter(owner_node_id=target.owner_node_id).count() >= settings.per_node_concurrency:
        return False
    return True


@transaction.atomic
def create_repository_operation_task(
    *,
    target_id: int,
    operation_type: str,
    trigger_type: str = Task.TriggerType.SYSTEM,
    due_at: datetime | None = None,
) -> RepositoryTask | None:
    if operation_type not in {value for value, _ in RepositoryTask.OperationType.choices}:
        raise ValidationError({"operation_type": "Unsupported repository operation."})
    target = RepositoryExecutionTarget.objects.select_for_update().select_related("repository").get(pk=target_id)
    if not target.is_active or target.active_task_id:
        return None
    operation_label = dict(RepositoryTask.OperationType.choices)[operation_type]
    task = create_task(
        organization_id=target.organization_id,
        task_type=Task.Type.REPOSITORY_OPERATION,
        display_name=f"{operation_label} · {target.repository.name}",
        trigger_type=trigger_type,
        request_payload={
            "repository_id": target.repository_id,
            "target_key": target.target_key,
            "operation_type": operation_type,
            "owner_identity": target.owner_identity,
        },
        resources=[
            {
                "resource_type": TaskResource.Type.REPOSITORY,
                "resource_id": target.repository_id,
                "is_primary": True,
            }
        ],
        normalize_trigger_type=False,
    )
    repository_task = RepositoryTask.objects.create(
        task=task,
        repository=target.repository,
        execution_target=target,
        operation_type=operation_type,
        owner_type=target.owner_type,
        owner_node_id=target.owner_node_id,
        owner_identity=target.owner_identity,
        due_at=due_at,
    )
    target.active_task = task
    target.save(update_fields=["active_task", "updated_at"])
    return repository_task


@transaction.atomic
def schedule_due_maintenance(*, now: datetime | None = None) -> list[int]:
    settings = maintenance_settings()
    if not settings.enabled:
        return []
    current = now or timezone.now()
    discover_repository_execution_targets(now=current)
    scheduled: list[int] = []
    targets = RepositoryExecutionTarget.objects.select_for_update().filter(is_active=True)
    for target in targets.order_by("target_key"):
        state = target.maintenance_state
        if target.active_task_id or (state.next_retry_at and state.next_retry_at > current):
            continue
        full_due = not state.next_full_due_at or state.next_full_due_at <= current
        quick_due = not state.next_quick_due_at or state.next_quick_due_at <= current
        operation = None
        full_window_due = full_due and _inside_full_window(current, settings)
        if full_window_due:
            window_open = current.astimezone(settings.timezone).replace(
                hour=settings.window_start.hour,
                minute=settings.window_start.minute,
                second=0,
                microsecond=0,
            )
            if settings.window_start > settings.window_end and current.astimezone(settings.timezone).time().replace(tzinfo=None) < settings.window_end:
                window_open -= timedelta(days=1)
            if current >= (window_open + _stable_full_delay(target.target_key, settings)).astimezone(
                datetime_timezone.utc
            ):
                operation = RepositoryTask.OperationType.MAINTENANCE_FULL
        if operation is None and quick_due and not full_window_due:
            operation = RepositoryTask.OperationType.MAINTENANCE_QUICK
        if operation is None or not _concurrency_available(target, settings):
            continue
        repository_task = create_repository_operation_task(
            target_id=target.id,
            operation_type=operation,
            trigger_type=(Task.TriggerType.RETRY if state.consecutive_failures else Task.TriggerType.SYSTEM),
            due_at=current,
        )
        if repository_task:
            scheduled.append(repository_task.id)
    return scheduled


def set_task_step(task: Task, step_name: str, *, status: str, progress: int) -> None:
    TaskStep.objects.filter(task=task, step_name=step_name).update(status=status, progress=progress)
    task.current_step = step_name
    task.progress = progress
    task.save(update_fields=["current_step", "progress", "updated_at"])
    append_task_event(task=task, step=task.steps.filter(step_name=step_name).first(), message=f"Step {step_name} {status}")


@transaction.atomic
def finalize_repository_operation(
    *,
    repository_task_id: int,
    succeeded: bool,
    result_payload: dict | None = None,
    error_code: str = "",
    error_message: str = "",
) -> Task:
    # ``execution_target`` is nullable for cleanup operations. Joining it in a
    # ``select_for_update()`` query therefore produces a LEFT OUTER JOIN, which
    # PostgreSQL refuses to lock ("FOR UPDATE cannot be applied to the nullable
    # side of an outer join"). Lock the repository task first, then lock the
    # required maintenance target explicitly.
    repository_task = (
        RepositoryTask.objects.select_for_update()
        .select_related("task")
        .get(pk=repository_task_id)
    )
    if repository_task.execution_target_id is None:
        raise ValidationError({"execution_target": "Repository maintenance requires an execution target."})
    task = repository_task.task
    target = RepositoryExecutionTarget.objects.select_for_update().get(
        pk=repository_task.execution_target_id
    )
    state = RepositoryMaintenanceState.objects.select_for_update().get(execution_target=target)
    settings = maintenance_settings()
    now = timezone.now()
    if succeeded:
        if repository_task.operation_type == RepositoryTask.OperationType.MAINTENANCE_QUICK:
            state.last_quick_success_at = now
            state.next_quick_due_at = now + settings.quick_interval
        elif repository_task.operation_type == RepositoryTask.OperationType.MAINTENANCE_FULL:
            state.last_full_success_at = now
            state.next_full_due_at = now + settings.full_interval
            state.next_quick_due_at = now + settings.quick_interval
        state.consecutive_failures = 0
        state.next_retry_at = None
        status = Task.Status.SUCCESS
    else:
        state.last_failure_at = now
        state.consecutive_failures += 1
        retry_seconds = min(3600, 60 * (2 ** min(state.consecutive_failures - 1, 6)))
        state.next_retry_at = now + timedelta(seconds=retry_seconds)
        status = Task.Status.FAILED
    state.save()
    if target.active_task_id == task.id:
        target.active_task = None
        target.save(update_fields=["active_task", "updated_at"])
    return complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=status,
        progress=100 if succeeded else task.progress,
        result_payload=result_payload,
        error_code=error_code,
        error_message=error_message[:2000],
    )


__all__ = [
    "create_repository_operation_task",
    "discover_repository_execution_targets",
    "finalize_repository_operation",
    "maintenance_settings",
    "schedule_due_maintenance",
    "set_task_step",
    "start_task",
]
