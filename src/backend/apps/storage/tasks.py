from __future__ import annotations

import logging

from celery import shared_task
from django.core.cache import cache

from common.observability.celery_context import logged_celery_task

from apps.storage.repositories.models import (
    Repository,
    RepositoryExecutionTarget,
    RepositoryTask,
)
from apps.storage.services.internal.repository_health import probe_repository_health
from apps.storage.services.internal.repository_usage import (
    sync_all_repositories,
    sync_organization_repositories,
)
from apps.storage.services.internal.kopia_cli import KopiaCliError, run_maintenance
from apps.storage.services.internal.repository_access import repository_payload_for_node
from apps.storage.services.internal.repository_agent_operation import (
    RepositoryAgentOperationResult,
    RepositoryAgentOperationStateUnknown,
    RepositoryAgentOperationTimeout,
    resolve_or_dispatch_repository_agent_operation,
)
from apps.storage.services.internal.repository_operations import (
    finalize_repository_operation,
    maintenance_settings,
    schedule_due_maintenance,
    set_task_step,
)
from apps.storage.services.internal.repository_secrets import scrub_secrets
from apps.task.models import Task, TaskStep
from apps.task.services.interface import start_task
from apps.task.services.recovery import (
    CONTROL_PLANE_RESTART_INTERRUPTED,
    RecoveryDecision,
    RecoveryPlan,
    record_recovery_decision,
)


logger = logging.getLogger(__name__)

_REPOSITORY_HEALTH_LOCK_TIMEOUT_SECONDS = 300
_REPOSITORY_OPERATION_LOCK_TIMEOUT_SECONDS = 600


def _repository_health_lock(repository_id: int) -> str:
    return f"storage:repository-health:repository:{int(repository_id)}"


@shared_task(name="apps.storage.tasks.reconcile_storage_repositories")
@logged_celery_task(
    name="apps.storage.tasks.reconcile_storage_repositories",
    trace_keys=("organization_id", "repo_type", "limit", "force"),
)
def reconcile_storage_repositories(
    *,
    organization_id: int | None = None,
    repository_ids: list[int] | None = None,
    repo_type: str | None = None,
    limit: int = 200,
    force: bool = False,
    stale_after_seconds: int | None = 900,
):
    """Refresh repository capacity and usage metrics for dashboards and alerts."""
    if organization_id is not None:
        result = sync_organization_repositories(
            organization_id=int(organization_id),
            repository_ids=repository_ids or None,
            repo_type=repo_type,
            limit=limit,
            force=force,
            stale_after_seconds=stale_after_seconds,
        )
    else:
        result = sync_all_repositories(
            repo_type=repo_type,
            limit=limit,
            force=force,
            stale_after_seconds=stale_after_seconds,
        )
    return {
        "repositories_scanned": result.get("repositories_synced", 0),
        "snapshots_upserted": 0,
        "snapshots_marked_deleted": 0,
    }


@shared_task(name="apps.storage.tasks.dispatch_repository_health_checks")
@logged_celery_task(name="apps.storage.tasks.dispatch_repository_health_checks")
def dispatch_repository_health_checks():
    """Fan out one lightweight health task per eligible repository."""
    repository_ids = list(
        Repository.objects.filter(
            status=Repository.Status.CREATED,
            repo_type__in=[
                Repository.Type.S3,
                Repository.Type.NAS,
                Repository.Type.PROXY_FS,
            ],
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    dispatched = 0
    for repository_id in repository_ids:
        try:
            check_storage_repository_health.apply_async(
                kwargs={"repository_id": repository_id}
            )
            dispatched += 1
        except Exception:
            logger.exception(
                "failed to enqueue repository health check repository_id=%s",
                repository_id,
            )
    return {"dispatched": dispatched}


@shared_task(name="apps.storage.tasks.check_storage_repository_health")
@logged_celery_task(
    name="apps.storage.tasks.check_storage_repository_health",
    trace_keys=("repository_id",),
)
def check_storage_repository_health(*, repository_id: int):
    """Run one health cycle and update only the repository health field."""
    lock_key = _repository_health_lock(repository_id)
    if not cache.add(lock_key, "1", timeout=_REPOSITORY_HEALTH_LOCK_TIMEOUT_SECONDS):
        return {"repository_id": repository_id, "status": "skipped", "locked": True}

    try:
        repository = (
            Repository.objects.filter(
                id=repository_id,
                status=Repository.Status.CREATED,
                repo_type__in=[
                    Repository.Type.S3,
                    Repository.Type.NAS,
                    Repository.Type.PROXY_FS,
                ],
            )
            .first()
        )
        if repository is None:
            return {
                "repository_id": repository_id,
                "status": "skipped",
                "eligible": False,
            }
        try:
            health = probe_repository_health(repository)
        except Exception as exc:
            health = Repository.Health.OFFLINE
            logger.warning(
                "repository health check failed repository_id=%s error_type=%s",
                repository_id,
                type(exc).__name__,
            )
        current_scope = Repository.objects.filter(
            pk=repository_id,
            status=Repository.Status.CREATED,
            repo_type=repository.repo_type,
            bind_node_type=repository.bind_node_type,
            bind_node_id=repository.bind_node_id,
            updated_at=repository.updated_at,
        )
        if repository.health != health:
            if not current_scope.update(health=health):
                return {
                    "repository_id": repository_id,
                    "status": "skipped",
                    "stale": True,
                }
        elif not current_scope.exists():
            return {
                "repository_id": repository_id,
                "status": "skipped",
                "stale": True,
            }
        return {"repository_id": repository_id, "status": health}
    finally:
        cache.delete(lock_key)


@shared_task(name="apps.storage.tasks.schedule_repository_maintenance")
@logged_celery_task(name="apps.storage.tasks.schedule_repository_maintenance")
def schedule_repository_maintenance():
    repository_task_ids = schedule_due_maintenance()
    for repository_task_id in repository_task_ids:
        execute_repository_operation.apply_async(kwargs={"repository_task_id": repository_task_id})
    return {"scheduled": len(repository_task_ids), "repository_task_ids": repository_task_ids}


@shared_task(name="apps.storage.tasks.reconcile_repository_operations")
@logged_celery_task(
    name="apps.storage.tasks.reconcile_repository_operations",
    trace_keys=("limit",),
)
def reconcile_repository_operations(*, limit: int = 100):
    """Requeue active Agent-backed repository operations for one idempotent advance."""
    repository_task_ids = list(
        RepositoryTask.objects.filter(
            owner_type=RepositoryExecutionTarget.OwnerType.NODE,
            task__status__in=[Task.Status.PENDING, Task.Status.RUNNING],
        )
        .order_by("task__updated_at", "id")
        .values_list("id", flat=True)[: max(1, int(limit))]
    )
    for repository_task_id in repository_task_ids:
        execute_repository_operation.apply_async(
            kwargs={"repository_task_id": repository_task_id}
        )
    return {
        "scanned": len(repository_task_ids),
        "redispatched": len(repository_task_ids),
        "repository_task_ids": repository_task_ids,
    }


@shared_task(name="apps.storage.tasks.execute_repository_operation")
@logged_celery_task(
    name="apps.storage.tasks.execute_repository_operation",
    trace_keys=("repository_task_id",),
)
def execute_repository_operation(*, repository_task_id: int):
    lock_key = f"storage:repository-operation:advance:{int(repository_task_id)}"
    if not cache.add(lock_key, "1", timeout=_REPOSITORY_OPERATION_LOCK_TIMEOUT_SECONDS):
        return {"status": "already_running", "repository_task_id": repository_task_id}
    try:
        return _execute_repository_operation(repository_task_id=repository_task_id)
    finally:
        cache.delete(lock_key)


def _execute_repository_operation(*, repository_task_id: int):
    repository_task = RepositoryTask.objects.select_related(
        "task", "repository", "execution_target"
    ).get(pk=repository_task_id)
    if repository_task.operation_type in {
        RepositoryTask.OperationType.CLEANUP_TARGET,
        RepositoryTask.OperationType.CLEANUP_REPOSITORY,
    }:
        from apps.storage.services.internal.repository_cleanup import (
            run_repository_cleanup_task,
        )

        return run_repository_cleanup_task(repository_task_id=repository_task.id)
    task = repository_task.task
    if task.status in {Task.Status.SUCCESS, Task.Status.FAILED, Task.Status.CANCELLED, Task.Status.TIMEOUT}:
        return {"status": task.status, "idempotent": True}
    started_now = task.status == Task.Status.PENDING
    if started_now:
        start_task(task_uuid=task.task_uuid, organization_id=task.organization_id)
        set_task_step(task, "prepare_repository_operation", status=TaskStep.Status.SUCCESS, progress=10)
        set_task_step(task, "verify_repository_owner", status=TaskStep.Status.SUCCESS, progress=20)
        set_task_step(task, "run_repository_operation", status=TaskStep.Status.RUNNING, progress=25)
    elif task.status == Task.Status.RUNNING:
        if repository_task.owner_type == RepositoryExecutionTarget.OwnerType.CONTROLLER:
            return {"status": task.status, "idempotent": True}
    else:
        return {"status": task.status, "idempotent": True}
    try:
        operation = _execute_maintenance(
            repository_task,
            allow_dispatch=started_now,
        )
        if operation.waiting:
            return {
                "status": "waiting",
                "repository_task_id": repository_task.id,
                "remote_task_id": str(operation.node_task_id),
            }
        result = operation.result
        set_task_step(task, "run_repository_operation", status=TaskStep.Status.SUCCESS, progress=80)
        set_task_step(task, "refresh_repository_usage", status=TaskStep.Status.RUNNING, progress=85)
        sync_organization_repositories(
            organization_id=repository_task.repository.organization_id,
            repository_ids=[repository_task.repository_id],
            limit=1,
            force=True,
            stale_after_seconds=None,
        )
        set_task_step(task, "refresh_repository_usage", status=TaskStep.Status.SUCCESS, progress=95)
        set_task_step(task, "finalize_repository_operation", status=TaskStep.Status.SUCCESS, progress=100)
        finalize_repository_operation(
            repository_task_id=repository_task.id,
            succeeded=True,
            result_payload=scrub_secrets(result),
        )
        return {"status": "success", "repository_task_id": repository_task.id}
    except RepositoryAgentOperationStateUnknown as exc:
        record_recovery_decision(
            task=task,
            plan=RecoveryPlan(
                decision=RecoveryDecision.FAIL,
                reason=str(exc),
                evidence={
                    "current_step": task.current_step,
                    "operation_type": repository_task.operation_type,
                },
            ),
        )
        set_task_step(
            task,
            task.current_step or "run_repository_operation",
            status=TaskStep.Status.FAILED,
            progress=int(task.progress),
        )
        finalize_repository_operation(
            repository_task_id=repository_task.id,
            succeeded=False,
            error_code=CONTROL_PLANE_RESTART_INTERRUPTED,
            error_message=str(exc),
        )
        return {"status": "failed", "repository_task_id": repository_task.id}
    except Exception as exc:
        set_task_step(
            task,
            task.current_step or "run_repository_operation",
            status=TaskStep.Status.FAILED,
            progress=int(task.progress),
        )
        finalize_repository_operation(
            repository_task_id=repository_task.id,
            succeeded=False,
            error_code=_repository_operation_error_code(exc),
            error_message=str(scrub_secrets(str(exc))),
        )
        return {"status": "failed", "repository_task_id": repository_task.id}


def _execute_maintenance(
    repository_task: RepositoryTask,
    *,
    allow_dispatch: bool = True,
) -> RepositoryAgentOperationResult:
    if repository_task.operation_type not in {
        RepositoryTask.OperationType.MAINTENANCE_QUICK,
        RepositoryTask.OperationType.MAINTENANCE_FULL,
    }:
        raise ValueError(f"Operation {repository_task.operation_type} is not implemented")
    full = repository_task.operation_type == RepositoryTask.OperationType.MAINTENANCE_FULL
    settings = maintenance_settings()
    if repository_task.owner_type == RepositoryExecutionTarget.OwnerType.CONTROLLER:
        result = run_maintenance(
            repository_task.repository,
            full=full,
            owner_identity=repository_task.owner_identity,
            timeout_seconds=settings.execution_timeout_seconds,
        )
        return RepositoryAgentOperationResult(
            waiting=False,
            node_task_id=repository_task.remote_task_id,
            result={
                "operation_type": repository_task.operation_type,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )

    from apps.node.models import Node
    node = Node.objects.filter(
        id=repository_task.owner_node_id,
        organization_id=repository_task.repository.organization_id,
        is_deleted=False,
    ).first()
    if node is None:
        raise ValueError("Repository owner node was not found")
    inventory = (node.metadata or {}).get("inventory") if isinstance(node.metadata, dict) else {}
    capabilities = inventory.get("capabilities") if isinstance(inventory, dict) else []
    if "repository_operation_v1" not in (capabilities if isinstance(capabilities, list) else []):
        raise ValueError("Repository owner does not advertise repository_operation_v1")
    repository_payload = repository_payload_for_node(
        repository=repository_task.repository,
        node=node,
        source_type="proxy" if node.role == "proxy" else "agent",
        source_ref_id=node.id,
    )
    outcome = resolve_or_dispatch_repository_agent_operation(
        repository_task=repository_task,
        node=node,
        payload={
            "operation_type": repository_task.operation_type,
            "owner_identity": repository_task.owner_identity,
            "repository": repository_payload,
        },
        correlation_type="repository_operation",
        timeout_seconds=settings.execution_timeout_seconds,
        allow_dispatch=allow_dispatch,
    )
    return RepositoryAgentOperationResult(
        waiting=outcome.waiting,
        node_task_id=outcome.node_task_id,
        result=scrub_secrets(outcome.result),
    )


def _repository_operation_error_code(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, RepositoryAgentOperationTimeout)):
        return "REPOSITORY_OPERATION_TIMEOUT"
    if isinstance(exc, KopiaCliError):
        return "KOPIA_MAINTENANCE_FAILED"
    return "REPOSITORY_OPERATION_FAILED"
