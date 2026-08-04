"""Async repository create / NAS repair bind-remount via RepositoryTask.

HTTP create/repair acceptance returns quickly with ``status=creating``; a Celery
worker runs the previously synchronous initialize/remount work and finalizes the
repository row to ``created`` or ``create_failed`` (or ``created``+offline for
remount failures on an already-bound repository).
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.storage.repositories.models import (
    Credential,
    Repository,
    RepositoryExecutionTarget,
    RepositoryTask,
)
from apps.storage.services.internal.nas_repository import (
    NASRepositoryError,
    initialize_proxy_nas_repository,
    validate_proxy_for_repository,
)
from apps.storage.services.internal.proxy_fs_repository import (
    ProxyFSRepositoryError,
    initialize_proxy_fs_repository,
    validate_proxy_for_proxy_fs,
)
from apps.storage.services.internal.repository_errors import (
    REPOSITORY_ALREADY_EXISTS_CODE,
    RepositoryAlreadyExistsError,
)
from apps.storage.services.internal.repository_initializer import (
    RepositoryInitializationError,
    initialize_s3_repository,
)
from apps.storage.services.internal.repository_secrets import (
    scrub_secrets,
    secret_values_for_scrub,
)
from apps.storage.services.internal.repository_task_naming import (
    repository_operation_display_name,
)
from apps.storage.services.internal.repository_usage import (
    enqueue_repository_usage_refresh,
    sync_repository_usage,
)
from apps.task.models import Task, TaskResource, TaskStep
from apps.task.services.interface import complete_task, create_task, start_task

logger = logging.getLogger(__name__)

ACTIVE_TASK_STATUSES = (Task.Status.PENDING, Task.Status.RUNNING)

CREATE_STEPS = (
    "prepare_repository_create",
    "verify_repository_owner",
    "initialize_repository",
    "finalize_repository_create",
)

CREATE_OPERATION_TYPES = frozenset(
    {
        RepositoryTask.OperationType.CREATE_REPOSITORY,
        RepositoryTask.OperationType.REPAIR_BIND,
        RepositoryTask.OperationType.REPAIR_REMOUNT,
    }
)


def repository_create_task_payload(repository_task: RepositoryTask) -> dict[str, Any]:
    task = repository_task.task
    return {
        "task_uuid": str(task.task_uuid),
        "status": task.status,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "operation_type": repository_task.operation_type,
    }


def active_repository_create_task(repository: Repository) -> RepositoryTask | None:
    return (
        RepositoryTask.objects.filter(
            repository=repository,
            operation_type__in=CREATE_OPERATION_TYPES,
            task__status__in=ACTIVE_TASK_STATUSES,
        )
        .select_related("task")
        .order_by("-created_at", "-id")
        .first()
    )


def preflight_bound_proxy(*, repository: Repository) -> Node:
    """Fail fast before enqueue when the bound Proxy cannot run init."""
    if repository.repo_type == Repository.Type.PROXY_FS:
        return validate_proxy_for_proxy_fs(repository)
    if repository.repo_type == Repository.Type.NAS:
        return validate_proxy_for_repository(repository)
    raise ValidationError("Repository type does not require a bound proxy.")


def enqueue_repository_create_task(
    *,
    repository: Repository,
    operation_type: str = RepositoryTask.OperationType.CREATE_REPOSITORY,
    requested_by=None,
    dispatch: bool = True,
    remount_previous_node_id: int | None = None,
) -> RepositoryTask:
    if operation_type not in CREATE_OPERATION_TYPES:
        raise ValidationError({"operation_type": "Unsupported repository create operation."})

    existing = active_repository_create_task(repository)
    if existing is not None:
        return existing

    with transaction.atomic():
        locked = Repository.objects.select_for_update().get(
            pk=repository.id,
            organization_id=repository.organization_id,
        )
        active = active_repository_create_task(locked)
        if active is not None:
            return active
        if locked.status not in {
            Repository.Status.CREATING,
            Repository.Status.CREATE_FAILED,
        }:
            # Remount may briefly set CREATING from CREATED; create path starts CREATING.
            if locked.status != Repository.Status.CREATED or operation_type != (
                RepositoryTask.OperationType.REPAIR_REMOUNT
            ):
                raise ValidationError(
                    {
                        "detail": (
                            f"Repository in status {locked.status} cannot accept "
                            f"operation {operation_type}."
                        )
                    }
                )

        owner_type, owner_node_id, owner_identity, target = _resolve_create_owner(locked)
        if locked.status != Repository.Status.CREATING:
            locked.status = Repository.Status.CREATING
            locked.save(update_fields=["status", "updated_at"])

        action_label = {
            RepositoryTask.OperationType.CREATE_REPOSITORY: "Create Repository",
            RepositoryTask.OperationType.REPAIR_BIND: "Bind Proxy",
            RepositoryTask.OperationType.REPAIR_REMOUNT: "Remount Repository",
        }[operation_type]

        request_payload: dict[str, Any] = {
            "repository_id": locked.id,
            "operation_type": operation_type,
            "repo_type": locked.repo_type,
            "bind_node_id": locked.bind_node_id,
        }
        if remount_previous_node_id is not None:
            request_payload["previous_bind_node_id"] = int(remount_previous_node_id)

        task = create_task(
            organization_id=locked.organization_id,
            task_type=Task.Type.REPOSITORY_OPERATION,
            display_name=repository_operation_display_name(
                action_label=action_label,
                repository=locked,
                target=target,
            ),
            trigger_type=Task.TriggerType.MANUAL,
            request_payload=request_payload,
            resources=[
                {
                    "resource_type": TaskResource.Type.REPOSITORY,
                    "resource_id": locked.id,
                    "is_primary": True,
                }
            ],
            steps=list(CREATE_STEPS),
            normalize_trigger_type=False,
        )
        repository_task = RepositoryTask.objects.create(
            task=task,
            repository=locked,
            execution_target=target,
            requested_by_id=getattr(requested_by, "id", None),
            operation_type=operation_type,
            owner_type=owner_type,
            owner_node_id=owner_node_id,
            owner_identity=owner_identity,
            due_at=timezone.now(),
        )
        if target is not None:
            if target.active_task_id:
                active_status = Task.objects.filter(pk=target.active_task_id).values_list(
                    "status", flat=True
                ).first()
                if active_status in {
                    Task.Status.SUCCESS,
                    Task.Status.FAILED,
                    Task.Status.CANCELLED,
                    Task.Status.TIMEOUT,
                }:
                    target.active_task = None
                else:
                    raise ValidationError(
                        {
                            "detail": (
                                f"Repository target {target.target_key} already has an active task."
                            )
                        }
                    )
            target.active_task = task
            target.is_active = True
            target.save(update_fields=["active_task", "is_active", "updated_at"])

        if dispatch:
            transaction.on_commit(lambda: _dispatch_create_task(repository_task.id))
        return repository_task


def run_repository_create_task(*, repository_task_id: int) -> dict[str, Any]:
    repository_task = RepositoryTask.objects.select_related(
        "task", "repository", "execution_target"
    ).get(pk=repository_task_id)
    task = repository_task.task
    if task.status in {
        Task.Status.SUCCESS,
        Task.Status.FAILED,
        Task.Status.CANCELLED,
        Task.Status.TIMEOUT,
    }:
        return {"status": task.status, "idempotent": True}

    if task.status == Task.Status.PENDING:
        start_task(task_uuid=task.task_uuid, organization_id=task.organization_id)
        task.refresh_from_db()

    repository = repository_task.repository
    _set_create_step(task, "prepare_repository_create", TaskStep.Status.SUCCESS, 10)
    _set_create_step(task, "verify_repository_owner", TaskStep.Status.RUNNING, 20)

    try:
        if repository_task.operation_type != RepositoryTask.OperationType.REPAIR_REMOUNT:
            if repository.repo_type in {Repository.Type.NAS, Repository.Type.PROXY_FS}:
                preflight_bound_proxy(repository=repository)
        _set_create_step(task, "verify_repository_owner", TaskStep.Status.SUCCESS, 35)
        _set_create_step(task, "initialize_repository", TaskStep.Status.RUNNING, 45)

        if repository_task.operation_type == RepositoryTask.OperationType.REPAIR_REMOUNT:
            _run_repair_remount(repository_task)
        else:
            _run_initialize(repository)

        _set_create_step(task, "initialize_repository", TaskStep.Status.SUCCESS, 85)
        _set_create_step(task, "finalize_repository_create", TaskStep.Status.RUNNING, 90)
        _finalize_create_success(repository_task)
        _set_create_step(task, "finalize_repository_create", TaskStep.Status.SUCCESS, 100)
        complete_task(
            task_uuid=task.task_uuid,
            organization_id=task.organization_id,
            status=Task.Status.SUCCESS,
            progress=100,
            result_payload={"repository_id": repository.id, "status": "created"},
        )
        _clear_target_active_task(repository_task)
        return {"status": "success", "repository_task_id": repository_task.id}
    except RepositoryAlreadyExistsError as exc:
        message = _safe_error_message(repository, str(exc))
        if repository_task.operation_type == RepositoryTask.OperationType.REPAIR_BIND:
            _fail_repair_bind_already_exists(repository_task, message=message)
        else:
            _fail_create_already_exists(repository_task, message=message)
        return {
            "status": "failed",
            "repository_task_id": repository_task.id,
            "error_code": REPOSITORY_ALREADY_EXISTS_CODE,
            "error": message,
        }
    except Exception as exc:
        message = _safe_error_message(repository, _exception_message(exc))
        error_code = _create_error_code(exc)
        _fail_create_keep_row(repository_task, error_code=error_code, message=message)
        return {
            "status": "failed",
            "repository_task_id": repository_task.id,
            "error_code": error_code,
            "error": message,
        }


def _resolve_create_owner(
    repository: Repository,
) -> tuple[str, int | None, str, RepositoryExecutionTarget | None]:
    if repository.repo_type == Repository.Type.S3:
        return (
            RepositoryExecutionTarget.OwnerType.CONTROLLER,
            None,
            "hfl-create@controller",
            None,
        )

    node_id = int(repository.bind_node_id or 0) or None
    if not node_id:
        raise ValidationError({"detail": "Bound proxy node is required for repository create."})

    target_key = f"repository:{repository.id}"
    target, _created = RepositoryExecutionTarget.objects.update_or_create(
        target_key=target_key,
        defaults={
            "organization_id": repository.organization_id,
            "repository": repository,
            "owner_type": RepositoryExecutionTarget.OwnerType.NODE,
            "owner_node_id": node_id,
            "owner_identity": f"hfl-create@node-{node_id}",
            "repository_subdir": "",
            "is_active": True,
        },
    )
    return (
        RepositoryExecutionTarget.OwnerType.NODE,
        node_id,
        f"hfl-create@node-{node_id}",
        target,
    )


def _run_initialize(repository: Repository) -> None:
    if repository.repo_type == Repository.Type.NAS:
        initialize_proxy_nas_repository(repository)
        return
    if repository.repo_type == Repository.Type.PROXY_FS:
        initialize_proxy_fs_repository(repository)
        return
    if repository.repo_type == Repository.Type.S3:
        initialize_s3_repository(repository)
        return
    raise ValidationError(f"Unsupported repository type for create: {repository.repo_type}")


def _run_repair_remount(repository_task: RepositoryTask) -> None:
    from apps.storage.services.internal.nas_repair import (
        _remount_on_new_proxy,
        _unmount_on_old_proxy,
    )

    repository = repository_task.repository
    payload = repository_task.task.request_payload or {}
    previous_node_id = payload.get("previous_bind_node_id")
    new_node = Node.objects.filter(
        id=repository.bind_node_id,
        organization_id=repository.organization_id,
        role=NodeRole.PROXY,
        is_deleted=False,
    ).first()
    if new_node is None:
        raise ValidationError("Bound proxy node not found.")
    if new_node.status != Node.Status.ONLINE:
        raise ValidationError(f'Bound proxy node "{new_node.name}" is not online.')

    _remount_on_new_proxy(
        organization_id=repository.organization_id,
        repository=repository,
        new_node=new_node,
    )
    if previous_node_id:
        _unmount_on_old_proxy(
            organization_id=repository.organization_id,
            repository=repository,
            old_node_id=int(previous_node_id),
        )


def _finalize_create_success(repository_task: RepositoryTask) -> None:
    with transaction.atomic():
        repository = Repository.objects.select_for_update().get(
            pk=repository_task.repository_id
        )
        repository.status = Repository.Status.CREATED
        repository.health = Repository.Health.ONLINE
        repository.last_checked_at = timezone.now()
        repository.save(update_fields=["status", "health", "last_checked_at", "updated_at"])
    repository = Repository.objects.get(pk=repository_task.repository_id)
    if repository.repo_type == Repository.Type.PROXY_FS:
        sync_repository_usage(repository)
    else:
        enqueue_repository_usage_refresh(
            organization_id=repository.organization_id,
            repository_ids=[repository.id],
            force=True,
            trigger="storage.repository.create_async",
        )


def _fail_repair_bind_already_exists(repository_task: RepositoryTask, *, message: str) -> None:
    """Keep the unbound NAS row when bind discovers an existing Kopia repository."""
    task = repository_task.task
    repository = Repository.objects.filter(pk=repository_task.repository_id).first()
    _set_create_step(
        task,
        str(task.current_step or "initialize_repository"),
        TaskStep.Status.FAILED,
        max(1, int(task.progress or 0)),
    )
    if repository is not None:
        config = dict(repository.config or {})
        config.pop("proxy_mount_path", None)
        repository.config = config
        repository.bind_node_type = None
        repository.bind_node_id = None
        repository.status = Repository.Status.CREATED
        repository.health = Repository.Health.UNVERIFIED
        repository.save(
            update_fields=[
                "config",
                "bind_node_type",
                "bind_node_id",
                "status",
                "health",
                "updated_at",
            ]
        )
    complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=Task.Status.FAILED,
        progress=max(1, int(task.progress or 0)),
        error_code=REPOSITORY_ALREADY_EXISTS_CODE,
        error_message=message[:2000],
    )
    _clear_target_active_task(repository_task)


def _fail_create_already_exists(repository_task: RepositoryTask, *, message: str) -> None:
    task = repository_task.task
    repository = repository_task.repository
    credential_id = repository.credential_id
    _set_create_step(
        task,
        str(task.current_step or "initialize_repository"),
        TaskStep.Status.FAILED,
        max(1, int(task.progress or 0)),
    )
    # Finalize the platform task, then detach PROTECT'd execution-target links
    # before deleting the repository row.
    _clear_target_active_task(repository_task)
    complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=Task.Status.FAILED,
        progress=max(1, int(task.progress or 0)),
        error_code=REPOSITORY_ALREADY_EXISTS_CODE,
        error_message=message[:2000],
    )
    repository_id = int(repository.id)
    RepositoryTask.objects.filter(repository_id=repository_id).update(
        execution_target=None
    )
    RepositoryExecutionTarget.objects.filter(repository_id=repository_id).delete()
    Repository.objects.filter(pk=repository_id).delete()
    if credential_id:
        Credential.objects.filter(id=credential_id).delete()


def _fail_create_keep_row(
    repository_task: RepositoryTask,
    *,
    error_code: str,
    message: str,
) -> None:
    task = repository_task.task
    repository = Repository.objects.filter(pk=repository_task.repository_id).first()
    _set_create_step(
        task,
        str(task.current_step or "initialize_repository"),
        TaskStep.Status.FAILED,
        max(1, int(task.progress or 0)),
    )
    if repository is not None:
        if repository_task.operation_type == RepositoryTask.OperationType.REPAIR_REMOUNT:
            # Remount operates on an already-initialized repository identity.
            repository.status = Repository.Status.CREATED
            repository.health = Repository.Health.OFFLINE
        else:
            repository.status = Repository.Status.CREATE_FAILED
            repository.health = Repository.Health.OFFLINE
        repository.last_checked_at = timezone.now()
        repository.save(
            update_fields=["status", "health", "last_checked_at", "updated_at"]
        )
    complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=Task.Status.FAILED,
        progress=max(1, int(task.progress or 0)),
        error_code=error_code,
        error_message=message[:2000],
    )
    _clear_target_active_task(repository_task)


def _clear_target_active_task(repository_task: RepositoryTask) -> None:
    target = repository_task.execution_target
    if target is None:
        return
    if target.active_task_id == repository_task.task_id:
        target.active_task = None
        target.save(update_fields=["active_task", "updated_at"])


def _set_create_step(task: Task, step_name: str, status: str, progress: int) -> None:
    from apps.storage.services.internal.repository_operations import set_task_step

    task.refresh_from_db(fields=["current_step", "progress"])
    set_task_step(task, step_name, status=status, progress=progress)


def _dispatch_create_task(repository_task_id: int) -> None:
    from apps.storage.tasks import execute_repository_operation

    execute_repository_operation.apply_async(kwargs={"repository_task_id": repository_task_id})


def _exception_message(exc: Exception) -> str:
    if isinstance(exc, DRFValidationError):
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            parts = []
            for key, value in detail.items():
                if isinstance(value, (list, tuple)):
                    parts.append(f"{key}: {'; '.join(str(item) for item in value)}")
                else:
                    parts.append(f"{key}: {value}")
            if parts:
                return "; ".join(parts)
        return str(detail or exc)
    if isinstance(exc, ValidationError):
        messages = list(getattr(exc, "messages", []) or [])
        if messages:
            return "; ".join(str(item) for item in messages)
        return str(exc)
    return str(exc)


def _create_error_code(exc: Exception) -> str:
    if isinstance(exc, RepositoryAlreadyExistsError):
        return REPOSITORY_ALREADY_EXISTS_CODE
    if isinstance(exc, RepositoryInitializationError):
        return "REPOSITORY_S3_CREATE_FAILED"
    if isinstance(exc, (NASRepositoryError, ProxyFSRepositoryError)):
        return "REPOSITORY_CREATE_FAILED"
    if isinstance(exc, (ValidationError, DRFValidationError)):
        return "REPOSITORY_CREATE_INVALID"
    if isinstance(exc, TimeoutError):
        return "REPOSITORY_CREATE_TIMEOUT"
    return "REPOSITORY_CREATE_FAILED"


def _safe_error_message(repository: Repository, message: str) -> str:
    try:
        from apps.storage.services.internal.repository_secrets import (
            resolve_repository_secrets,
        )

        secrets_payload = resolve_repository_secrets(repository)
    except Exception:
        secrets_payload = {}
    return str(
        scrub_secrets(
            message,
            extra_values=secret_values_for_scrub(repository, secrets_payload),
        )
    )


__all__ = [
    "CREATE_OPERATION_TYPES",
    "active_repository_create_task",
    "enqueue_repository_create_task",
    "preflight_bound_proxy",
    "repository_create_task_payload",
    "run_repository_create_task",
]
