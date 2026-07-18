"""Unified backup source deletion with strict / force modes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.constants import AuditAction, AuditResult
from apps.audit.services.interface import write_audit_log
from apps.iam.models import Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal import redis_store
from apps.node.services.internal.node_registry import (
    CONNECTION_OFFLINE,
    agent_connection_status,
)
from apps.protection.models import (
    BackupConfig,
    BackupSourceSnapshot,
    BackupSourceSnapshotDirectory,
    SnapshotDownloadArtifact,
)
from apps.protection.services.snapshot_delete import (
    create_snapshot_delete_task,
    run_snapshot_delete_task,
)
from apps.restore.models import RestorePlan, RestoreRecord
from apps.source.constants import ResourceType, SelectableSourceKind
from apps.source.models import BackupSourceRepositoryPurgePending, SourceResource
from apps.source.services.internal.selectable_ids import parse_selectable_id
from apps.source.services.internal.source_pipeline import delete_pipeline_entry, purge_pipeline_entry
from apps.source.services.interface import unmount_resource
from apps.storage.repositories.models import Repository
from apps.storage.services.interface import (
    RepositoryCleanupBlocked,
    create_direct_nas_target_cleanup_task,
    direct_nas_cleanup_target_ids,
    repository_cleanup_task_payload,
    run_repository_cleanup_task,
)
from apps.task.models import Task, TaskResource, TaskStep
from apps.task.services.interface import append_task_step_event, complete_task, create_task, start_task

logger = logging.getLogger(__name__)

_ACTIVE_TASK_STATUSES = {
    Task.Status.PENDING,
    Task.Status.RUNNING,
}

_SOURCE_UNREGISTER_STEPS = [
    "prepare_source_unregister",
    "cleanup_direct_nas_repositories",
    "reset_backup_config",
    "cleanup_source_endpoint",
    "finalize_source_unregister",
]

_UNREGISTER_TERMINAL = {
    Task.Status.SUCCESS,
    Task.Status.FAILED,
    Task.Status.CANCELLED,
    Task.Status.TIMEOUT,
}


@dataclass
class DeleteReason:
    code: str
    detail: str
    source_id: str = ""
    source_name: str = ""
    repository_id: int | None = None
    repository_name: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "detail": self.detail}
        if self.source_id:
            payload["source_id"] = self.source_id
        if self.source_name:
            payload["source_name"] = self.source_name
        if self.repository_id is not None:
            payload["repository_id"] = self.repository_id
        if self.repository_name:
            payload["repository_name"] = self.repository_name
        return payload


@dataclass
class DeleteWarning:
    code: str
    detail: str
    source_id: str = ""
    source_name: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "detail": self.detail}
        if self.source_id:
            payload["source_id"] = self.source_id
        if self.source_name:
            payload["source_name"] = self.source_name
        return payload


@dataclass
class SourceDeleteContext:
    selectable_id: str
    source_kind: str
    source_ref_id: int
    source_type: str
    display_name: str
    agent_node: Node | None = None
    nas_resource: SourceResource | None = None

    @property
    def is_agent(self) -> bool:
        return self.source_kind == SelectableSourceKind.AGENT


class BackupSourceDeleteFailed(Exception):
    def __init__(
        self,
        *,
        message: str,
        reasons: list[DeleteReason],
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reasons = reasons
        self.hint = hint or (
            "Fix the issues above and try again, or enable force delete to continue."
        )


def _source_key(source_type: str, source_ref_id: int) -> str:
    kind = "agent" if source_type == "agent" else source_type
    return f"{kind}:{source_ref_id}"


def _resolve_context(*, organization_id: int, selectable_id: str) -> SourceDeleteContext | None:
    parsed = parse_selectable_id(selectable_id)
    if parsed is None or parsed[0] not in (SelectableSourceKind.AGENT, SelectableSourceKind.NAS):
        return None
    kind, ref_id = parsed
    if kind == SelectableSourceKind.AGENT:
        node = Node.objects.filter(
            pk=ref_id,
            organization_id=organization_id,
            is_deleted=False,
            role=NodeRole.AGENT,
        ).first()
        if node is None:
            return None
        return SourceDeleteContext(
            selectable_id=selectable_id,
            source_kind=kind,
            source_ref_id=ref_id,
            source_type="agent",
            display_name=str(node.name or selectable_id),
            agent_node=node,
        )
    resource = SourceResource.objects.filter(
        pk=ref_id,
        organization_id=organization_id,
        is_deleted=False,
        resource_type=ResourceType.NAS,
    ).first()
    if resource is None:
        return None
    return SourceDeleteContext(
        selectable_id=selectable_id,
        source_kind=kind,
        source_ref_id=ref_id,
        source_type="nas",
        display_name=str(resource.name or selectable_id),
        nas_resource=resource,
    )


def _running_tasks_for_source(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> list[Task]:
    from apps.node.services.internal.task_offline_reconcile import product_task_blocks_cleanup

    subtype_query = TaskResource.objects.filter(
        resource_type=TaskResource.Type.BACKUP_SOURCE,
        resource_id=source_ref_id,
    ).filter(
        models_Q_subtype(source_type),
    )
    task_ids = subtype_query.values_list("task_id", flat=True)
    tasks = list(
        Task.objects.filter(
            organization_id=organization_id,
            id__in=task_ids,
            status__in=_ACTIVE_TASK_STATUSES,
            task_type__in=[Task.Type.BACKUP, Task.Type.RESTORE],
        ).order_by("-created_at", "-id")
    )
    return [task for task in tasks if product_task_blocks_cleanup(task=task)]


def models_Q_subtype(source_type: str):
    from django.db.models import Q

    query = Q(resource_subtype=source_type)
    if source_type == "agent":
        query |= Q(resource_subtype="")
    return query


def _task_resources_join_subtype_q(source_type: str):
    from django.db.models import Q

    query = Q(resources__resource_subtype=source_type)
    if source_type == "agent":
        query |= Q(resources__resource_subtype="")
    return query


def _source_resource_defs(ids: list[str]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for selectable_id in ids:
        parsed = parse_selectable_id(selectable_id)
        if not parsed:
            continue
        source_type, source_ref_id = parsed
        if source_type not in {"agent", "nas"}:
            continue
        key = (source_type, int(source_ref_id))
        if key in seen:
            continue
        seen.add(key)
        resources.append(
            {
                "resource_type": TaskResource.Type.BACKUP_SOURCE,
                "resource_subtype": source_type,
                "resource_id": int(source_ref_id),
                "is_primary": True,
            }
        )
    return resources


def _create_source_unregister_task(
    *,
    org: Organization,
    selectable_id: str,
    force: bool,
) -> Task:
    display_name = "Unregister backup source"
    return create_task(
        organization_id=org.id,
        task_type=Task.Type.SOURCE_UNREGISTER,
        display_name=display_name,
        trigger_type=Task.TriggerType.MANUAL,
        request_payload={
            "source_ids": [selectable_id],
            "force": bool(force),
        },
        resources=_source_resource_defs([selectable_id]),
        steps=_SOURCE_UNREGISTER_STEPS,
    )


def _set_unregister_step(
    *,
    task: Task | None,
    step_name: str,
    status: str,
    progress: int,
    message: str,
    level: str = "INFO",
    metadata: dict[str, Any] | None = None,
) -> None:
    if task is None:
        return
    TaskStep.objects.filter(task=task, step_name=step_name).update(
        status=status,
        progress=Decimal("100.00") if status == TaskStep.Status.SUCCESS else Decimal(str(progress)),
    )
    task.current_step = step_name
    task.progress = Decimal(str(progress))
    task.save(update_fields=["current_step", "progress", "updated_at"])
    append_task_step_event(
        task=task,
        step_name=step_name,
        level=level,
        message=message,
        metadata=metadata,
    )


def _complete_unregister_task(
    *,
    task: Task | None,
    status: str,
    result_payload: dict[str, Any] | None = None,
    error_code: str = "",
    error_message: str = "",
) -> None:
    if task is None:
        return
    complete_task(
        task_uuid=task.task_uuid,
        organization_id=task.organization_id,
        status=status,
        progress=100 if status == Task.Status.SUCCESS else max(1, int(task.progress or 0)),
        result_payload=result_payload,
        error_code=error_code,
        error_message=error_message,
    )


def _active_unregister_task_for_source(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> Task | None:
    tasks = (
        Task.objects.filter(
            organization_id=organization_id,
            task_type=Task.Type.SOURCE_UNREGISTER,
            resources__resource_type=TaskResource.Type.BACKUP_SOURCE,
            resources__resource_subtype=source_type,
            resources__resource_id=source_ref_id,
        )
        .exclude(status__in=_UNREGISTER_TERMINAL)
        .order_by("-created_at", "-id")
        .distinct()
    )
    return tasks.first()


def _active_reset_task_for_source(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> Task | None:
    tasks = (
        Task.objects.filter(
            organization_id=organization_id,
            task_type=Task.Type.BACKUP_CONFIG_RESET,
            resources__resource_type=TaskResource.Type.BACKUP_SOURCE,
            resources__resource_subtype=source_type,
            resources__resource_id=source_ref_id,
        )
        .exclude(status__in=_UNREGISTER_TERMINAL)
        .order_by("-created_at", "-id")
        .distinct()
    )
    return tasks.first()


def source_needs_reset_protection(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> bool:
    from apps.source.constants import PipelineStep
    from apps.source.models import SourceBackupPipelineEntry

    if BackupConfig.objects.filter(
        organization_id=organization_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
    ).exists():
        return True
    config_ids = list(
        BackupConfig.objects.filter(
            organization_id=organization_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
        ).values_list("id", flat=True)
    )
    if config_ids and BackupSourceSnapshot.objects.filter(
        organization_id=organization_id,
        backup_config_id__in=config_ids,
    ).exclude(status=BackupSourceSnapshot.Status.DELETED).exists():
        return True
    if config_ids and RestorePlan.objects.filter(
        organization_id=organization_id,
        backup_config_id__in=config_ids,
    ).exists():
        return True
    endpoint = RestoreRecord.EndpointType.AGENT if source_type == "agent" else RestoreRecord.EndpointType.NAS
    if RestoreRecord.objects.filter(
        organization_id=organization_id,
        source_type=endpoint,
        source_ref_id=source_ref_id,
    ).exists():
        return True
    source_kind = SelectableSourceKind.AGENT if source_type == "agent" else source_type
    pipeline = SourceBackupPipelineEntry.objects.filter(
        organization_id=organization_id,
        source_kind=source_kind,
        ref_id=source_ref_id,
    ).first()
    return pipeline is not None and int(pipeline.step) == PipelineStep.READY


def _assert_strict_delete_blockers(*, ctx: SourceDeleteContext, force: bool) -> None:
    if force:
        return
    reasons: list[DeleteReason] = []
    if ctx.is_agent and ctx.agent_node is not None:
        if agent_connection_status(node=ctx.agent_node) == CONNECTION_OFFLINE:
            reasons.append(
                DeleteReason(
                    code="agent_offline",
                    detail=(
                        f"Agent \"{ctx.display_name}\" is offline — remote uninstall is required "
                        "in strict mode."
                    ),
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                )
            )
    if ctx.nas_resource is not None and ctx.nas_resource.mount_status == "mounted":
        proxy = ctx.nas_resource.bound_node
        if proxy is None or proxy.status != Node.Status.ONLINE:
            reasons.append(
                DeleteReason(
                    code="proxy_offline",
                    detail=(
                        f"Proxy for \"{ctx.display_name}\" is offline — NAS unmount is required "
                        "in strict mode."
                    ),
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                )
            )
    if reasons:
        raise BackupSourceDeleteFailed(message="Backup source was not deleted.", reasons=reasons)


def _normalize_delete_ids(ids: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in ids:
        key = str(value).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    if not normalized:
        raise BackupSourceDeleteFailed(
            message="No backup sources were specified.",
            reasons=[DeleteReason(code="empty_ids", detail="ids must not be empty.")],
        )
    return normalized


def _prepare_delete_batch(
    *,
    org: Organization,
    ids: list[str],
    force: bool,
    executing_task_uuid: str | None = None,
) -> list[tuple[SourceDeleteContext, dict[str, int], list[DeleteWarning]]]:
    prepared: list[tuple[SourceDeleteContext, dict[str, int], list[DeleteWarning]]] = []
    for selectable_id in ids:
        ctx = _resolve_context(organization_id=org.id, selectable_id=selectable_id)
        if ctx is None:
            raise BackupSourceDeleteFailed(
                message="Backup source was not deleted.",
                reasons=[
                    DeleteReason(
                        code="source_not_found",
                        detail="Backup source was not found.",
                        source_id=selectable_id,
                    )
                ],
            )
        active_unregister = _active_unregister_task_for_source(
            organization_id=org.id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        )
        if active_unregister is not None and (
            not executing_task_uuid or str(active_unregister.task_uuid) != executing_task_uuid
        ):
            raise BackupSourceDeleteFailed(
                message="Backup source was not deleted.",
                reasons=[
                    DeleteReason(
                        code="unregister_in_progress",
                        detail="A source unregister task is already running.",
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    )
                ],
            )
        if _active_reset_task_for_source(
            organization_id=org.id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        ):
            raise BackupSourceDeleteFailed(
                message="Backup source was not deleted.",
                reasons=[
                    DeleteReason(
                        code="reset_in_progress",
                        detail="A backup configuration reset is already running.",
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    )
                ],
            )
        _assert_strict_delete_blockers(ctx=ctx, force=force)
        prepared.append((ctx, {}, []))
    return prepared


def _resolve_unregister_user(*, org: Organization, task: Task):
    payload = task.request_payload if isinstance(task.request_payload, dict) else {}
    user_id = int(payload.get("user_id") or 0)
    if user_id <= 0:
        return None
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(pk=user_id).first()


def _cleanup_direct_nas_for_unregister(
    *,
    org: Organization,
    ctx: SourceDeleteContext,
    unregister_task: Task,
    user,
) -> tuple[set[int], list[dict[str, Any]]]:
    configs = list(
        BackupConfig.objects.filter(
            organization_id=org.id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        ).values("id", "repository_id")
    )
    configs_by_repository: dict[int, list[int]] = {}
    repository_ids = {int(config["repository_id"]) for config in configs}
    repositories = {
        repository.id: repository
        for repository in Repository.objects.filter(
            organization_id=org.id,
            id__in=repository_ids,
        )
    }
    for config in configs:
        repository = repositories.get(int(config["repository_id"]))
        if repository is None:
            continue
        if (
            repository.repo_type != Repository.Type.NAS
            or repository.bind_node_id is not None
        ):
            continue
        configs_by_repository.setdefault(repository.id, []).append(int(config["id"]))

    cleaned_repository_ids: set[int] = set()
    cleanup_tasks: list[dict[str, Any]] = []
    for repository_id, config_ids in configs_by_repository.items():
        repository = repositories[repository_id]
        target_ids = direct_nas_cleanup_target_ids(
            repository=repository,
            backup_config_ids=config_ids,
            owner_node_id=ctx.agent_node.id if ctx.agent_node is not None else None,
        )
        if not target_ids:
            raise BackupSourceDeleteFailed(
                message="Direct NAS repository cleanup failed.",
                reasons=[
                    DeleteReason(
                        code="repository_cleanup_target_missing",
                        detail="The Direct NAS physical repository target could not be resolved.",
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                        repository_id=repository.id,
                        repository_name=repository.name,
                    )
                ],
            )
        for target_id in target_ids:
            try:
                repository_task = create_direct_nas_target_cleanup_task(
                    repository=repository,
                    target_id=target_id,
                    triggered_by_task=unregister_task,
                    requested_by=user,
                    dispatch=False,
                )
            except RepositoryCleanupBlocked as exc:
                details = "; ".join(
                    str(item.get("detail") or item.get("code") or "cleanup blocked")
                    for item in exc.preflight.get("blockers", [])
                )
                raise BackupSourceDeleteFailed(
                    message="Direct NAS repository cleanup was blocked.",
                    reasons=[
                        DeleteReason(
                            code="repository_cleanup_blocked",
                            detail=details or "Repository cleanup was blocked.",
                            source_id=ctx.selectable_id,
                            source_name=ctx.display_name,
                            repository_id=repository.id,
                            repository_name=repository.name,
                        )
                    ],
                ) from exc
            except Exception as exc:
                raise BackupSourceDeleteFailed(
                    message="Direct NAS repository cleanup failed.",
                    reasons=[
                        DeleteReason(
                            code="repository_cleanup_create_failed",
                            detail=str(exc),
                            source_id=ctx.selectable_id,
                            source_name=ctx.display_name,
                            repository_id=repository.id,
                            repository_name=repository.name,
                        )
                    ],
                ) from exc

            run_repository_cleanup_task(repository_task_id=repository_task.id)
            repository_task.task.refresh_from_db()
            cleanup_tasks.append(repository_cleanup_task_payload(repository_task))
            if repository_task.task.status != Task.Status.SUCCESS:
                raise BackupSourceDeleteFailed(
                    message="Direct NAS repository cleanup failed.",
                    reasons=[
                        DeleteReason(
                            code=repository_task.task.error_code or "repository_cleanup_failed",
                            detail=(
                                repository_task.task.error_message
                                or "Physical repository cleanup failed."
                            ),
                            source_id=ctx.selectable_id,
                            source_name=ctx.display_name,
                            repository_id=repository.id,
                            repository_name=repository.name,
                        )
                    ],
                )
        cleaned_repository_ids.add(repository.id)
    return cleaned_repository_ids, cleanup_tasks


def _execute_source_unregister_work(
    *,
    org: Organization,
    prepared: list[tuple[SourceDeleteContext, dict[str, int], list[DeleteWarning]]],
    force: bool,
    user,
    unregister_task: Task,
) -> dict[str, Any]:
    normalized = [ctx.selectable_id for ctx, _, _ in prepared]
    _set_unregister_step(
        task=unregister_task,
        step_name="cleanup_direct_nas_repositories",
        status=TaskStep.Status.RUNNING,
        progress=20,
        message="Cleaning Direct NAS physical repositories",
    )

    deleted: list[str] = []
    per_source: list[dict[str, Any]] = []
    pending_after_commit: list[tuple[str, int]] = []
    all_warnings: list[dict[str, Any]] = []
    aggregate_cleanup: dict[str, int] = {
        "snapshots_purged": 0,
        "repository_blobs_deleted": 0,
        "repository_purge_pending": 0,
        "backup_configs_removed": 0,
        "snapshots_removed": 0,
        "restore_plans_removed": 0,
        "restore_records_removed": 0,
        "tasks_orphaned": 0,
    }
    direct_cleanup_by_source: dict[str, list[dict[str, Any]]] = {}

    try:
        prepared_for_finalize: list[
            tuple[SourceDeleteContext, dict[str, int], list[DeleteWarning]]
        ] = []
        for ctx, _blob_stats, _warnings in prepared:
            cleaned_repository_ids, cleanup_tasks = _cleanup_direct_nas_for_unregister(
                org=org,
                ctx=ctx,
                unregister_task=unregister_task,
                user=user,
            )
            direct_cleanup_by_source[ctx.selectable_id] = cleanup_tasks
            blob_stats, warnings, reasons = _prepare_single_source_snapshot_cleanup(
                organization_id=org.id,
                ctx=ctx,
                force=force,
                skip_repository_ids=cleaned_repository_ids,
            )
            if reasons:
                raise BackupSourceDeleteFailed(
                    message="Backup source was not deleted.",
                    reasons=reasons,
                )
            prepared_for_finalize.append((ctx, blob_stats, warnings))
        _set_unregister_step(
            task=unregister_task,
            step_name="cleanup_direct_nas_repositories",
            status=TaskStep.Status.SUCCESS,
            progress=30,
            message="Direct NAS repository cleanup completed",
            metadata={"cleanup_tasks": direct_cleanup_by_source},
        )
        _set_unregister_step(
            task=unregister_task,
            step_name="reset_backup_config",
            status=TaskStep.Status.RUNNING,
            progress=35,
            message="Resetting backup configuration data",
        )
        with transaction.atomic():
            for ctx, blob_stats, warnings in prepared_for_finalize:
                summary = _finalize_single_source_delete(
                    org=org,
                    ctx=ctx,
                    blob_stats=blob_stats,
                    warnings=warnings,
                    force=force,
                    user=user,
                )
                summary["repository_cleanup_tasks"] = direct_cleanup_by_source.get(
                    ctx.selectable_id, []
                )
                per_source.append(summary)
                all_warnings.extend(summary.get("warnings") or [])
                cleanup = summary.get("cleanup") or {}
                for key in aggregate_cleanup:
                    aggregate_cleanup[key] += int(cleanup.get(key) or 0)
                if summary.get("pending_removal"):
                    pending_after_commit.append((ctx.selectable_id, int(summary["node_id"])))
                else:
                    deleted.append(ctx.selectable_id)
    except BackupSourceDeleteFailed as exc:
        _set_unregister_step(
            task=unregister_task,
            step_name=str(unregister_task.current_step or "reset_backup_config"),
            status=TaskStep.Status.FAILED,
            progress=max(1, int(unregister_task.progress or 0)),
            message=exc.message,
            level="ERROR",
            metadata={"reasons": [reason.as_dict() for reason in exc.reasons], "hint": exc.hint},
        )
        _complete_unregister_task(
            task=unregister_task,
            status=Task.Status.FAILED,
            result_payload={"source_ids": normalized, "reasons": [reason.as_dict() for reason in exc.reasons]},
            error_code="SOURCE_UNREGISTER_FAILED",
            error_message=exc.message,
        )
        raise

    _set_unregister_step(
        task=unregister_task,
        step_name="reset_backup_config",
        status=TaskStep.Status.SUCCESS,
        progress=60,
        message="Backup configuration data reset",
        metadata={"cleanup": aggregate_cleanup},
    )
    _set_unregister_step(
        task=unregister_task,
        step_name="cleanup_source_endpoint",
        status=TaskStep.Status.RUNNING,
        progress=70,
        message="Cleaning up source endpoints",
    )

    pending_removals: list[dict[str, Any]] = []
    if pending_after_commit:
        from apps.node.services.internal.node_lifecycle import NodeLifecycleError, start_node_remove

        for selectable_id, node_id in pending_after_commit:
            node = Node.objects.filter(
                pk=node_id,
                organization_id=org.id,
                is_deleted=False,
            ).first()
            if node is None:
                deleted.append(selectable_id)
                continue
            try:
                removal = start_node_remove(org=org, node=node, user=user)
                pending_removals.append(
                    {
                        "source_id": selectable_id,
                        "node_id": node.id,
                        "task_id": removal.get("task_id"),
                        "operation_id": removal.get("operation_id"),
                        "state": removal.get("state") or "removing",
                    }
                )
            except NodeLifecycleError as exc:
                logger.warning(
                    "backup source delete lifecycle dispatch failed source=%s node=%s: %s",
                    selectable_id,
                    node_id,
                    exc,
                )
                ctx = _resolve_context(organization_id=org.id, selectable_id=selectable_id)
                if ctx is not None:
                    _soft_delete_identity(org=org, ctx=ctx, user=user)
                deleted.append(selectable_id)
                all_warnings.append(
                    {
                        "code": getattr(exc, "code", "lifecycle_rejected"),
                        "detail": str(exc),
                        "source_id": selectable_id,
                    }
                )

    if pending_removals and not deleted:
        result = "pending"
    elif pending_removals or all_warnings:
        result = "partial_success"
    else:
        result = "success"
    _set_unregister_step(
        task=unregister_task,
        step_name="cleanup_source_endpoint",
        status=TaskStep.Status.SUCCESS,
        progress=85,
        message="Source endpoint cleanup dispatched",
        metadata={"pending_removals": pending_removals, "warnings": all_warnings},
    )
    _set_unregister_step(
        task=unregister_task,
        step_name="finalize_source_unregister",
        status=TaskStep.Status.SUCCESS,
        progress=100,
        message="Source unregister finalized",
        metadata={"result": result, "deleted": deleted},
    )
    write_audit_log(
        organization=org,
        user=user,
        action=AuditAction.DELETE,
        resource_type="backup_source",
        resource_id=",".join(deleted),
        resource_name=f"{len(deleted)} source(s)",
        result=AuditResult.SUCCESS,
        metadata={
            "force": force,
            "result": result,
            "deleted": deleted,
            "cleanup": aggregate_cleanup,
            "warnings": all_warnings,
        },
    )
    response = {
        "ok": True,
        "accepted": False,
        "result": result,
        "deleted": deleted,
        "pending_removals": pending_removals,
        "warnings": all_warnings,
        "cleanup": aggregate_cleanup,
        "repository_cleanup_tasks": [
            item
            for cleanup_tasks in direct_cleanup_by_source.values()
            for item in cleanup_tasks
        ],
        "sources": per_source,
        "task_id": unregister_task.id,
        "task_uuid": str(unregister_task.task_uuid),
    }
    _complete_unregister_task(
        task=unregister_task,
        status=Task.Status.SUCCESS,
        result_payload=response,
    )
    return response


def queue_delete_backup_sources(
    *,
    org: Organization,
    ids: list[str],
    force: bool = False,
    user=None,
) -> dict[str, Any]:
    """Validate, create source_unregister task, and queue async execution."""
    normalized = _normalize_delete_ids(ids)
    _prepare_delete_batch(org=org, ids=normalized, force=force)

    user_id = getattr(user, "id", None)
    unregister_tasks: list[Task] = []
    with transaction.atomic():
        for selectable_id in normalized:
            unregister_task = _create_source_unregister_task(
                org=org,
                selectable_id=selectable_id,
                force=force,
            )
            payload = dict(unregister_task.request_payload or {})
            if user_id:
                payload["user_id"] = int(user_id)
            unregister_task.request_payload = payload
            unregister_task.save(update_fields=["request_payload", "updated_at"])

            start_task(task_uuid=unregister_task.task_uuid, organization_id=org.id)
            _set_unregister_step(
                task=unregister_task,
                step_name="prepare_source_unregister",
                status=TaskStep.Status.SUCCESS,
                progress=15,
                message="Source unregister prepared",
                metadata={"source_ids": [selectable_id], "force": bool(force)},
            )
            unregister_tasks.append(unregister_task)

    from apps.source.tasks.source_unregister import execute_source_unregister_task

    def _dispatch(task_id: int) -> None:
        execute_source_unregister_task.delay(task_id=task_id)

    from django.conf import settings

    if getattr(settings, "SOURCE_UNREGISTER_EAGER", False):
        results = [
            run_source_unregister_task(organization_id=org.id, task_uuid=str(task.task_uuid))
            for task in unregister_tasks
        ]
        deleted = [item for result in results for item in result.get("deleted", [])]
        pending_removals = [item for result in results for item in result.get("pending_removals", [])]
        warnings = [item for result in results for item in result.get("warnings", [])]
        sources = [item for result in results for item in result.get("sources", [])]
        accepted = False
        result = "completed"
    else:
        for task in unregister_tasks:
            transaction.on_commit(lambda task_id=task.id: _dispatch(task_id))
        deleted = []
        pending_removals = []
        warnings = []
        sources = []
        accepted = True
        result = "pending"

    first_task = unregister_tasks[0]

    return {
        "ok": True,
        "accepted": accepted,
        "result": result,
        "deleted": deleted,
        "pending_removals": pending_removals,
        "warnings": warnings,
        "cleanup": {},
        "sources": sources,
        "task_id": first_task.id,
        "task_uuid": str(first_task.task_uuid),
        "task_ids": [task.id for task in unregister_tasks],
        "task_uuids": [str(task.task_uuid) for task in unregister_tasks],
        "status": Task.Status.RUNNING if accepted else Task.Status.SUCCESS,
        "source_ids": normalized,
    }


def run_source_unregister_task(*, organization_id: int, task_uuid: str) -> dict[str, Any]:
    task = Task.objects.filter(organization_id=organization_id, task_uuid=task_uuid).first()
    if task is None:
        raise Task.DoesNotExist
    if task.status in _UNREGISTER_TERMINAL:
        return task.result_payload if isinstance(task.result_payload, dict) else {}

    org = Organization.objects.filter(pk=organization_id).first()
    if org is None:
        raise Task.DoesNotExist

    payload = task.request_payload if isinstance(task.request_payload, dict) else {}
    normalized = [str(value).strip() for value in payload.get("source_ids") or [] if str(value).strip()]
    force = bool(payload.get("force"))
    user = _resolve_unregister_user(org=org, task=task)
    try:
        if not normalized:
            raise BackupSourceDeleteFailed(
                message="Backup source was not deleted.",
                reasons=[DeleteReason(code="empty_ids", detail="ids must not be empty.")],
            )
        prepared = _prepare_delete_batch(
            org=org,
            ids=normalized,
            force=force,
            executing_task_uuid=str(task.task_uuid),
        )
    except BackupSourceDeleteFailed as exc:
        _set_unregister_step(
            task=task,
            step_name=str(task.current_step or "prepare_source_unregister"),
            status=TaskStep.Status.FAILED,
            progress=max(1, int(task.progress or 0)),
            message=exc.message,
            level="ERROR",
            metadata={"reasons": [reason.as_dict() for reason in exc.reasons], "hint": exc.hint},
        )
        _complete_unregister_task(
            task=task,
            status=Task.Status.FAILED,
            result_payload={
                "source_ids": normalized,
                "reasons": [reason.as_dict() for reason in exc.reasons],
            },
            error_code="SOURCE_UNREGISTER_PREFLIGHT_FAILED",
            error_message=exc.message,
        )
        raise
    return _execute_source_unregister_work(
        org=org,
        prepared=prepared,
        force=force,
        user=user,
        unregister_task=task,
    )


def preflight_delete_backup_sources(
    *,
    organization_id: int,
    ids: list[str],
) -> dict[str, Any]:
    """Return strict-mode risks for UI (offline agent, unreachable repo, running tasks)."""
    risks: list[dict[str, Any]] = []
    blocking: list[dict[str, Any]] = []
    for selectable_id in ids:
        ctx = _resolve_context(organization_id=organization_id, selectable_id=selectable_id)
        if ctx is None:
            blocking.append(
                DeleteReason(
                    code="source_not_found",
                    detail="Backup source was not found.",
                    source_id=selectable_id,
                ).as_dict()
            )
            continue
        running = _running_tasks_for_source(
            organization_id=organization_id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        )
        if running:
            blocking.append(
                DeleteReason(
                    code="running_tasks",
                    detail=f"{len(running)} backup or restore task(s) are still running.",
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                ).as_dict()
            )
        if _active_unregister_task_for_source(
            organization_id=organization_id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        ):
            blocking.append(
                DeleteReason(
                    code="unregister_in_progress",
                    detail="A source unregister task is already running.",
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                ).as_dict()
            )
        if _active_reset_task_for_source(
            organization_id=organization_id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        ):
            blocking.append(
                DeleteReason(
                    code="reset_in_progress",
                    detail="A backup configuration reset is already running.",
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                ).as_dict()
            )
        if ctx.is_agent and ctx.agent_node is not None:
            from apps.node.services.internal.node_lifecycle import _active_lifecycle_task

            org = Organization.objects.filter(pk=organization_id).first()
            if org and _active_lifecycle_task(org=org, node=ctx.agent_node):
                blocking.append(
                    DeleteReason(
                        code="lifecycle_in_progress",
                        detail="A lifecycle operation is already in progress.",
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    ).as_dict()
                )
            from apps.node.services.internal.node_workload import get_node_workload_blockers

            for blocker in get_node_workload_blockers(node=ctx.agent_node):
                blocking.append(
                    DeleteReason(
                        code="node_workload_active",
                        detail=blocker.label,
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    ).as_dict()
                )
            status = agent_connection_status(node=ctx.agent_node)
            if status == CONNECTION_OFFLINE:
                risks.append(
                    DeleteReason(
                        code="agent_offline",
                        detail="Agent is offline — remote uninstall cannot complete in strict mode.",
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    ).as_dict()
                )
        if ctx.nas_resource is not None:
            resource = ctx.nas_resource
            config_ids = list(
                BackupConfig.objects.filter(
                    organization_id=organization_id,
                    source_type=ctx.source_type,
                    source_ref_id=ctx.source_ref_id,
                ).values_list("id", flat=True)
            )
            if config_ids and resource.bound_node_id is None:
                risks.append(
                    DeleteReason(
                        code="proxy_unbound",
                        detail=(
                            f"NAS source \"{ctx.display_name}\" has no bound Proxy. "
                            "Strict unregister may fail if repository cleanup is required."
                        ),
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    ).as_dict()
                )
            elif (
                resource.bound_node_id is None
                and str(resource.status_message or "").strip().lower() == "needs_proxy"
            ):
                risks.append(
                    DeleteReason(
                        code="proxy_unbound",
                        detail=(
                            f"NAS source \"{ctx.display_name}\" requires a Proxy but none is bound. "
                            "Strict unregister may fail."
                        ),
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    ).as_dict()
                )
            if resource.mount_status == "mounted":
                proxy = resource.bound_node
                if proxy is None or proxy.status != Node.Status.ONLINE:
                    risks.append(
                        DeleteReason(
                            code="proxy_offline",
                            detail="Proxy is offline — NAS unmount cannot complete in strict mode.",
                            source_id=ctx.selectable_id,
                            source_name=ctx.display_name,
                        ).as_dict()
                    )
        for risk in _repository_unreachable_preflight_risks(
            organization_id=organization_id,
            ctx=ctx,
        ):
            risks.append(risk.as_dict())
    return {
        "risks": risks,
        "blocking": blocking,
        "strict_may_fail": bool(risks),
        "delete_disabled": bool(blocking),
    }


def _repository_unreachable_preflight_risks(
    *,
    organization_id: int,
    ctx: SourceDeleteContext,
) -> list[DeleteReason]:
    """Warn only when a linked repository is offline — snapshot cleanup is automatic on delete."""
    config_ids = list(
        BackupConfig.objects.filter(
            organization_id=organization_id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        ).values_list("id", flat=True)
    )
    if not config_ids:
        return []
    snapshots = list(
        BackupSourceSnapshot.objects.filter(
            organization_id=organization_id,
            backup_config_id__in=config_ids,
        ).exclude(status=BackupSourceSnapshot.Status.DELETED)
    )
    if not snapshots:
        return []
    risks: list[DeleteReason] = []
    seen_repos: set[int] = set()
    for snapshot in snapshots:
        repo_id = int(snapshot.repository_id)
        if repo_id in seen_repos:
            continue
        seen_repos.add(repo_id)
        repo = Repository.objects.filter(
            organization_id=organization_id,
            id=repo_id,
        ).first()
        if repo is None or repo.health != Repository.Health.OFFLINE:
            continue
        repo_name = str(repo.name or repo_id)
        risks.append(
            DeleteReason(
                code="repository_unreachable",
                detail=(
                    f"Target repository \"{repo_name}\" is offline. Strict delete may fail; "
                    "use force delete to remove the source and queue cleanup."
                ),
                source_id=ctx.selectable_id,
                source_name=ctx.display_name,
                repository_id=repo_id,
                repository_name=repo_name,
            )
        )
    return risks


def _snapshot_delete_error_detail(task: Task, result: dict[str, Any]) -> str:
    parts: list[str] = []
    last_error = str(getattr(task, "last_error", "") or "").strip()
    if last_error:
        parts.append(last_error)
    item_results = result.get("results") if isinstance(result.get("results"), list) else []
    for item in item_results:
        if not isinstance(item, dict) or str(item.get("status") or "") != "failed":
            continue
        snapshot_id = str(item.get("kopia_snapshot_id") or "").strip()
        item_error = str(item.get("error_message") or "").strip()
        if snapshot_id and item_error:
            parts.append(f"{snapshot_id}: {item_error}")
        elif item_error:
            parts.append(item_error)
    task_uuid = str(getattr(task, "task_uuid", "") or "").strip()
    if task_uuid:
        parts.append(f"(task {task_uuid})")
    if parts:
        return " ".join(parts)[:2000]
    return "One or more physical snapshots failed to delete."


def _snapshot_delete_strict(
    *,
    source_snapshot: BackupSourceSnapshot,
) -> tuple[bool, str | None]:
    if source_snapshot.status == BackupSourceSnapshot.Status.DELETED:
        return True, None
    task = create_snapshot_delete_task(
        source_snapshot=source_snapshot,
        trigger_type=Task.TriggerType.SYSTEM,
    )
    result = run_snapshot_delete_task(
        organization_id=source_snapshot.organization_id,
        task_uuid=str(task.task_uuid),
        source_snapshot_id=source_snapshot.id,
    )
    task.refresh_from_db()
    failed_count = int(result.get("failed_count") or 0)
    if failed_count > 0:
        return False, _snapshot_delete_error_detail(task, result if isinstance(result, dict) else {})
    source_snapshot.refresh_from_db()
    if source_snapshot.status != BackupSourceSnapshot.Status.DELETED:
        return False, _snapshot_delete_error_detail(task, result if isinstance(result, dict) else {}) or (
            "Snapshot delete did not finalize."
        )
    return True, None


def _enqueue_repository_purge_pending(
    *,
    organization_id: int,
    ctx: SourceDeleteContext,
    repository_id: int,
    snapshot_ids: list[int],
    kopia_snapshot_ids: list[str],
    error: str,
) -> None:
    BackupSourceRepositoryPurgePending.objects.create(
        organization_id=organization_id,
        source_kind=ctx.source_kind,
        source_ref_id=ctx.source_ref_id,
        repository_id=repository_id,
        payload={
            "source_snapshot_ids": snapshot_ids,
            "kopia_snapshot_ids": kopia_snapshot_ids,
            "error": error[:2000],
        },
        last_error=error[:2000],
    )


def _delete_repository_snapshots(
    *,
    organization_id: int,
    ctx: SourceDeleteContext,
    force: bool,
    reasons: list[DeleteReason],
    warnings: list[DeleteWarning],
    skip_repository_ids: set[int] | None = None,
) -> dict[str, int]:
    configs = list(
        BackupConfig.objects.filter(
            organization_id=organization_id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        ).values_list("id", flat=True)
    )
    if not configs:
        return {"snapshots_purged": 0, "repository_blobs_deleted": 0, "repository_purge_pending": 0}

    snapshots = list(
        BackupSourceSnapshot.objects.filter(
            organization_id=organization_id,
            backup_config_id__in=configs,
        ).exclude(status=BackupSourceSnapshot.Status.DELETED)
    )
    blobs_deleted = 0
    pending_count = 0
    skipped_repositories = {int(value) for value in (skip_repository_ids or set())}
    for snapshot in snapshots:
        repo = Repository.objects.filter(
            organization_id=organization_id,
            id=snapshot.repository_id,
        ).first()
        repo_name = str(repo.name if repo else snapshot.repository_id)
        if int(snapshot.repository_id) in skipped_repositories:
            blobs_deleted += 1
            continue
        ok, err = _snapshot_delete_strict(source_snapshot=snapshot)
        if ok:
            blobs_deleted += 1
            continue
        detail = err or "Repository snapshot delete failed."
        if not force:
            reasons.append(
                DeleteReason(
                    code="repository_snapshot_delete_failed",
                    detail=detail,
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                    repository_id=int(snapshot.repository_id),
                    repository_name=repo_name,
                )
            )
            continue
        rows = BackupSourceSnapshotDirectory.objects.filter(source_snapshot=snapshot)
        kopia_ids = [
            str(row.kopia_snapshot_id)
            for row in rows
            if str(row.kopia_snapshot_id or "").strip()
        ]
        _enqueue_repository_purge_pending(
            organization_id=organization_id,
            ctx=ctx,
            repository_id=int(snapshot.repository_id),
            snapshot_ids=[snapshot.id],
            kopia_snapshot_ids=kopia_ids,
            error=detail,
        )
        pending_count += 1
        warnings.append(
            DeleteWarning(
                code="repository_purge_pending",
                detail=f"Backup data cleanup queued for repository \"{repo_name}\".",
                source_id=ctx.selectable_id,
                source_name=ctx.display_name,
            )
        )
    return {
        "snapshots_purged": blobs_deleted,
        "repository_blobs_deleted": blobs_deleted,
        "repository_purge_pending": pending_count,
    }


def _purge_protection_db(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> dict[str, int]:
    configs = list(
        BackupConfig.objects.filter(
            organization_id=organization_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
        ).values_list("id", flat=True)
    )
    config_ids = configs
    if not config_ids:
        RestoreRecord.objects.filter(
            organization_id=organization_id,
            source_type=source_type if source_type != "agent" else RestoreRecord.EndpointType.AGENT,
            source_ref_id=source_ref_id,
        ).delete()
        return {
            "backup_configs_removed": 0,
            "snapshots_removed": 0,
            "restore_plans_removed": 0,
            "restore_records_removed": 0,
        }

    endpoint = RestoreRecord.EndpointType.AGENT if source_type == "agent" else RestoreRecord.EndpointType.NAS
    restore_records_removed = RestoreRecord.objects.filter(
        organization_id=organization_id,
        source_type=endpoint,
        source_ref_id=source_ref_id,
    ).delete()[0]
    restore_plans_removed = RestorePlan.objects.filter(
        organization_id=organization_id,
        backup_config_id__in=config_ids,
    ).delete()[0]
    snapshots_removed = BackupSourceSnapshot.objects.filter(
        organization_id=organization_id,
        backup_config_id__in=config_ids,
    ).delete()[0]
    backup_configs_removed = BackupConfig.objects.filter(id__in=config_ids).delete()[0]
    return {
        "backup_configs_removed": backup_configs_removed,
        "snapshots_removed": snapshots_removed,
        "restore_plans_removed": restore_plans_removed,
        "restore_records_removed": restore_records_removed,
    }


def _cleanup_download_artifacts(*, organization_id: int, config_ids: list[int]) -> int:
    if not config_ids:
        return 0
    snapshot_dir_ids = BackupSourceSnapshotDirectory.objects.filter(
        organization_id=organization_id,
        backup_config_id__in=config_ids,
    ).values_list("id", flat=True)
    if not snapshot_dir_ids:
        return 0
    artifacts = SnapshotDownloadArtifact.objects.filter(
        organization_id=organization_id,
        source_snapshot_directory_id__in=list(snapshot_dir_ids),
    )
    count = artifacts.count()
    for artifact in artifacts:
        task = artifact.task
        artifact.delete()
        if task is not None:
            task.delete()
    return count


def _strict_nas_umount(
    *,
    ctx: SourceDeleteContext,
    force: bool,
    reasons: list[DeleteReason],
    warnings: list[DeleteWarning],
) -> dict[str, Any]:
    resource = ctx.nas_resource
    if resource is None or resource.mount_status != "mounted":
        return {"skipped": True}
    result = unmount_resource(resource=resource)
    if result.get("success"):
        return {"success": True}
    message = str(result.get("message") or "NAS unmount failed.")
    if force:
        warnings.append(
            DeleteWarning(
                code="nas_umount_failed",
                detail=f"{message} Check the proxy host manually.",
                source_id=ctx.selectable_id,
                source_name=ctx.display_name,
            )
        )
        return {"skipped": True}
    reasons.append(
        DeleteReason(
            code="nas_umount_failed",
            detail=message,
            source_id=ctx.selectable_id,
            source_name=ctx.display_name,
        )
    )
    return {"failed": True}


def _mark_tasks_orphaned(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
    source_name: str,
) -> int:
    return _mark_task_payload_flag(
        organization_id=organization_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
        flag_at="source_orphaned_at",
        reason_key="source_orphaned_reason",
        flag_reason="source_removed",
        extra={"source_orphan_display_name": source_name},
        skip_if="source_orphaned_at",
    )


def _mark_tasks_reconfigured(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> int:
    return _mark_task_payload_flag(
        organization_id=organization_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
        flag_at="source_reconfigured_at",
        reason_key="source_reconfigured_reason",
        flag_reason="revert_to_configuration",
        skip_if="source_reconfigured_at",
    )


def _mark_task_payload_flag(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
    flag_at: str,
    reason_key: str,
    flag_reason: str,
    skip_if: str,
    extra: dict[str, str] | None = None,
) -> int:
    tasks = Task.objects.filter(
        organization_id=organization_id,
        resources__resource_type=TaskResource.Type.BACKUP_SOURCE,
        resources__resource_id=source_ref_id,
    ).filter(_task_resources_join_subtype_q(source_type)).distinct()
    now_iso = timezone.now().isoformat()
    updated = 0
    for task in tasks:
        payload = dict(task.request_payload) if isinstance(task.request_payload, dict) else {}
        if payload.get(skip_if):
            continue
        payload[flag_at] = now_iso
        payload[reason_key] = flag_reason
        if extra:
            payload.update(extra)
        task.request_payload = payload
        task.save(update_fields=["request_payload", "updated_at"])
        updated += 1
    return updated


def _soft_delete_identity(
    *,
    org: Organization,
    ctx: SourceDeleteContext,
    user,
) -> None:
    if ctx.is_agent and ctx.agent_node is not None:
        node = ctx.agent_node
        for resource in SourceResource.objects.filter(
            organization_id=org.id,
            bound_node=node,
            is_deleted=False,
        ):
            write_audit_log(
                organization=org,
                user=user,
                action=AuditAction.DELETE,
                resource_type="source_resource",
                resource_id=str(resource.id),
                resource_name=resource.name,
                result=AuditResult.SUCCESS,
                metadata={"reason": "backup_source_delete", "node_id": node.id},
            )
            resource.soft_delete()
        redis_store.clear_agent_location(agent_id=node.id)
        delete_pipeline_entry(
            organization_id=org.id,
            source_kind=SelectableSourceKind.AGENT,
            ref_id=node.id,
        )
        write_audit_log(
            organization=org,
            user=user,
            action=AuditAction.DELETE,
            resource_type="node",
            resource_id=str(node.id),
            resource_name=node.name,
            result=AuditResult.SUCCESS,
            metadata={"role": node.role, "reason": "backup_source_delete"},
        )
        node.soft_delete()
        return

    resource = ctx.nas_resource
    if resource is None:
        return
    write_audit_log(
        organization=org,
        user=user,
        action=AuditAction.DELETE,
        resource_type="source_resource",
        resource_id=str(resource.id),
        resource_name=resource.name,
        result=AuditResult.SUCCESS,
        metadata={"reason": "backup_source_delete"},
    )
    purge_pipeline_entry(
        organization_id=org.id,
        source_kind=SelectableSourceKind.NAS,
        ref_id=resource.id,
    )
    resource.delete()


def _finalize_single_source_delete(
    *,
    org: Organization,
    ctx: SourceDeleteContext,
    blob_stats: dict[str, int],
    warnings: list[DeleteWarning],
    force: bool,
    user,
) -> dict[str, Any]:
    reasons: list[DeleteReason] = []

    config_ids = list(
        BackupConfig.objects.filter(
            organization_id=org.id,
            source_type=ctx.source_type,
            source_ref_id=ctx.source_ref_id,
        ).values_list("id", flat=True)
    )
    _cleanup_download_artifacts(organization_id=org.id, config_ids=config_ids)

    db_stats = _purge_protection_db(
        organization_id=org.id,
        source_type=ctx.source_type,
        source_ref_id=ctx.source_ref_id,
    )

    if ctx.nas_resource is not None:
        umount_result = _strict_nas_umount(ctx=ctx, force=force, reasons=reasons, warnings=warnings)
        if umount_result.get("failed"):
            raise BackupSourceDeleteFailed(message="Backup source was not deleted.", reasons=reasons)

    tasks_orphaned = _mark_tasks_orphaned(
        organization_id=org.id,
        source_type=ctx.source_type,
        source_ref_id=ctx.source_ref_id,
        source_name=ctx.display_name,
    )

    cleanup = {**blob_stats, **db_stats, "tasks_orphaned": tasks_orphaned}
    warning_payload = [warning.as_dict() for warning in warnings]

    if ctx.is_agent and ctx.agent_node is not None:
        node = ctx.agent_node
        conn = agent_connection_status(node=node)
        if conn == CONNECTION_OFFLINE:
            if not force:
                reasons.append(
                    DeleteReason(
                        code="agent_offline",
                        detail=f"Agent \"{ctx.display_name}\" is offline — remote uninstall is required in strict mode.",
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
                    )
                )
                raise BackupSourceDeleteFailed(message="Backup source was not deleted.", reasons=reasons)
            warnings.append(
                DeleteWarning(
                    code="agent_offline",
                    detail=f"Agent \"{ctx.display_name}\" is offline — uninstall was skipped.",
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                )
            )
            _soft_delete_identity(org=org, ctx=ctx, user=user)
            return {
                "source_id": ctx.selectable_id,
                "source_name": ctx.display_name,
                "cleanup": cleanup,
                "warnings": [warning.as_dict() for warning in warnings],
            }
        return {
            "source_id": ctx.selectable_id,
            "source_name": ctx.display_name,
            "pending_removal": True,
            "node_id": node.id,
            "cleanup": cleanup,
            "warnings": warning_payload,
        }

    _soft_delete_identity(org=org, ctx=ctx, user=user)

    return {
        "source_id": ctx.selectable_id,
        "source_name": ctx.display_name,
        "cleanup": cleanup,
        "warnings": warning_payload,
    }


def _prepare_single_source_snapshot_cleanup(
    *,
    organization_id: int,
    ctx: SourceDeleteContext,
    force: bool,
    skip_repository_ids: set[int] | None = None,
) -> tuple[dict[str, int], list[DeleteWarning], list[DeleteReason]]:
    reasons: list[DeleteReason] = []
    warnings: list[DeleteWarning] = []
    running = _running_tasks_for_source(
        organization_id=organization_id,
        source_type=ctx.source_type,
        source_ref_id=ctx.source_ref_id,
    )
    if running:
        reasons.append(
            DeleteReason(
                code="running_tasks",
                detail=f"{len(running)} backup or restore task(s) are still running.",
                source_id=ctx.selectable_id,
                source_name=ctx.display_name,
            )
        )
        return {}, warnings, reasons

    agent_reachable = (
        ctx.is_agent
        and ctx.agent_node is not None
        and agent_connection_status(node=ctx.agent_node) != CONNECTION_OFFLINE
    )
    blob_stats = _delete_repository_snapshots(
        organization_id=organization_id,
        ctx=ctx,
        force=force or agent_reachable,
        reasons=reasons,
        warnings=warnings,
        skip_repository_ids=skip_repository_ids,
    )
    return blob_stats, warnings, reasons


def delete_backup_sources(
    *,
    org: Organization,
    ids: list[str],
    force: bool = False,
    user=None,
) -> dict[str, Any]:
    """Synchronously unregister backup-selectable sources (tests and internal callers)."""
    normalized = _normalize_delete_ids(ids)
    prepared = _prepare_delete_batch(org=org, ids=normalized, force=force)

    if len(normalized) != 1:
        raise BackupSourceDeleteFailed(
            message="Synchronous source unregister accepts one source at a time.",
            reasons=[DeleteReason(code="batch_not_supported", detail="Provide exactly one source ID.")],
        )
    unregister_task = _create_source_unregister_task(
        org=org,
        selectable_id=normalized[0],
        force=force,
    )
    payload = dict(unregister_task.request_payload or {})
    user_id = getattr(user, "id", None)
    if user_id:
        payload["user_id"] = int(user_id)
    unregister_task.request_payload = payload
    unregister_task.save(update_fields=["request_payload", "updated_at"])

    start_task(task_uuid=unregister_task.task_uuid, organization_id=org.id)
    _set_unregister_step(
        task=unregister_task,
        step_name="prepare_source_unregister",
        status=TaskStep.Status.SUCCESS,
        progress=15,
        message="Source unregister prepared",
        metadata={"source_ids": normalized, "force": bool(force)},
    )
    return _execute_source_unregister_work(
        org=org,
        prepared=prepared,
        force=force,
        user=user,
        unregister_task=unregister_task,
    )


def reconcile_stuck_source_unregister_tasks(
    *,
    limit: int = 50,
    stale_seconds: int = 90,
) -> dict[str, int]:
    """Re-dispatch source-unregister Celery jobs left RUNNING after worker never consumed them."""
    from datetime import timedelta

    from apps.source.tasks.source_unregister import execute_source_unregister_task

    cutoff = timezone.now() - timedelta(seconds=max(30, int(stale_seconds)))
    stuck = list(
        Task.objects.filter(
            task_type=Task.Type.SOURCE_UNREGISTER,
            status=Task.Status.RUNNING,
            current_step="reset_backup_config",
            updated_at__lt=cutoff,
        )
        .order_by("updated_at", "id")[: max(1, int(limit))]
    )
    redispatched = 0
    for row in stuck:
        execute_source_unregister_task.delay(task_id=int(row.id))
        redispatched += 1
        logger.warning(
            "re-dispatched stuck source_unregister task id=%s uuid=%s updated_at=%s",
            row.id,
            row.task_uuid,
            row.updated_at,
        )
    return {"scanned": len(stuck), "redispatched": redispatched}


__all__ = [
    "BackupSourceDeleteFailed",
    "delete_backup_sources",
    "preflight_delete_backup_sources",
    "queue_delete_backup_sources",
    "reconcile_stuck_source_unregister_tasks",
    "run_source_unregister_task",
    "source_needs_reset_protection",
]
