"""Revert backup wizard pipeline steps with protection data cleanup."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.audit.constants import AuditAction, AuditResult
from apps.audit.services.interface import write_audit_log
from apps.iam.models import Organization
from apps.protection.models import BackupConfig
from apps.source.constants import PipelineStep, SelectableSourceKind
from apps.source.services.internal.backup_source_delete import (
    BackupSourceDeleteFailed,
    DeleteReason,
    DeleteWarning,
    _delete_repository_snapshots,
    _mark_tasks_reconfigured,
    _purge_protection_db,
    _resolve_context,
    _running_tasks_for_source,
)
from apps.node.services.internal.node_registry import (
    CONNECTION_OFFLINE,
    agent_connection_status,
)
from apps.source.services.internal.selectable_ids import parse_selectable_id
from apps.source.services.internal.source_pipeline import (
    delete_pipeline_entry,
    force_set_pipeline_steps,
)

logger = logging.getLogger(__name__)


def preflight_revert_backup_sources(
    *,
    organization_id: int,
    ids: list[str],
    target_step: int,
) -> dict[str, Any]:
    blocking: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
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
        if target_step == PipelineStep.SOURCE_POOL:
            if BackupConfig.objects.filter(
                organization_id=organization_id,
                source_type=ctx.source_type,
                source_ref_id=ctx.source_ref_id,
            ).exists():
                blocking.append(
                    DeleteReason(
                        code="backup_config_exists",
                        detail="Backup configuration exists — revert from Start Backup instead.",
                        source_id=ctx.selectable_id,
                        source_name=ctx.display_name,
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
    return {
        "blocking": blocking,
        "risks": risks,
        "revert_disabled": bool(blocking),
        "strict_may_fail": bool(risks),
    }


def _revert_step2_to_step1(*, organization_id: int, selectable_id: str) -> str:
    parsed = parse_selectable_id(selectable_id)
    if not parsed:
        raise BackupSourceDeleteFailed(
            message="Backup source was not reverted.",
            reasons=[DeleteReason(code="invalid_id", detail="Invalid source id.", source_id=selectable_id)],
        )
    source_kind, ref_id = parsed
    if BackupConfig.objects.filter(
        organization_id=organization_id,
        source_type="agent" if source_kind == SelectableSourceKind.AGENT else source_kind,
        source_ref_id=ref_id,
    ).exists():
        raise BackupSourceDeleteFailed(
            message="Backup source was not reverted.",
            reasons=[
                DeleteReason(
                    code="backup_config_exists",
                    detail="Backup configuration exists — revert from Start Backup instead.",
                    source_id=selectable_id,
                )
            ],
        )
    delete_pipeline_entry(
        organization_id=organization_id,
        source_kind=source_kind,
        ref_id=ref_id,
    )
    return selectable_id


def _revert_step3_to_step2(
    *,
    org: Organization,
    selectable_id: str,
    force: bool,
    user,
) -> dict[str, Any]:
    ctx = _resolve_context(organization_id=org.id, selectable_id=selectable_id)
    if ctx is None:
        raise BackupSourceDeleteFailed(
            message="Backup source was not reverted.",
            reasons=[
                DeleteReason(
                    code="source_not_found",
                    detail="Backup source was not found.",
                    source_id=selectable_id,
                )
            ],
        )
    reasons: list[DeleteReason] = []
    warnings: list[DeleteWarning] = []
    running = _running_tasks_for_source(
        organization_id=org.id,
        source_type=ctx.source_type,
        source_ref_id=ctx.source_ref_id,
    )
    if running:
        raise BackupSourceDeleteFailed(
            message="Backup source was not reverted.",
            reasons=[
                DeleteReason(
                    code="running_tasks",
                    detail=f"{len(running)} backup or restore task(s) are still running.",
                    source_id=ctx.selectable_id,
                    source_name=ctx.display_name,
                )
            ],
        )

    agent_reachable = (
        ctx.is_agent
        and ctx.agent_node is not None
        and agent_connection_status(node=ctx.agent_node) != CONNECTION_OFFLINE
    )
    blob_stats = _delete_repository_snapshots(
        organization_id=org.id,
        ctx=ctx,
        force=force or agent_reachable,
        reasons=reasons,
        warnings=warnings,
    )
    if reasons:
        raise BackupSourceDeleteFailed(message="Backup source was not reverted.", reasons=reasons)

    db_stats = _purge_protection_db(
        organization_id=org.id,
        source_type=ctx.source_type,
        source_ref_id=ctx.source_ref_id,
    )
    force_set_pipeline_steps(
        organization_id=org.id,
        ids=[ctx.selectable_id],
        step=PipelineStep.CONFIG,
    )
    tasks_marked = _mark_tasks_reconfigured(
        organization_id=org.id,
        source_type=ctx.source_type,
        source_ref_id=ctx.source_ref_id,
    )

    write_audit_log(
        organization=org,
        user=user,
        action=AuditAction.UPDATE,
        resource_type="backup_source",
        resource_id=ctx.selectable_id,
        resource_name=ctx.display_name,
        result=AuditResult.SUCCESS,
        metadata={
            "action": "revert",
            "target_step": PipelineStep.CONFIG,
            "force": force,
            "cleanup": {**blob_stats, **db_stats, "tasks_marked": tasks_marked},
            "warnings": [warning.as_dict() for warning in warnings],
        },
    )
    return {
        "source_id": ctx.selectable_id,
        "warnings": [warning.as_dict() for warning in warnings],
        "cleanup": {**blob_stats, **db_stats},
    }


def revert_backup_sources(
    *,
    org: Organization,
    ids: list[str],
    target_step: int,
    force: bool = False,
    user=None,
) -> dict[str, Any]:
    if target_step not in (PipelineStep.SOURCE_POOL, PipelineStep.CONFIG):
        raise ValueError("target_step must be 1 or 2")

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

    updated: list[str] = []
    all_warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        for selectable_id in normalized:
            if target_step == PipelineStep.SOURCE_POOL:
                updated.append(_revert_step2_to_step1(organization_id=org.id, selectable_id=selectable_id))
            else:
                summary = _revert_step3_to_step2(
                    org=org,
                    selectable_id=selectable_id,
                    force=force,
                    user=user,
                )
                updated.append(selectable_id)
                all_warnings.extend(summary.get("warnings") or [])

    return {
        "updated": updated,
        "target_step": target_step,
        "warnings": all_warnings,
        "result": "partial_success" if all_warnings else "success",
    }


__all__ = [
    "preflight_revert_backup_sources",
    "revert_backup_sources",
]
