"""Persist protection wizard pipeline step for real backup-selectable sources."""

from __future__ import annotations

from django.utils import timezone

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.source.constants import PipelineStep, ResourceType, SelectableSourceKind
from apps.source.models import SourceBackupPipelineEntry, SourceResource
from apps.source.services.internal.selectable_ids import parse_selectable_id


def _selectable_key(source_kind: str, ref_id: int) -> str:
    return f"{source_kind}:{ref_id}"


def load_pipeline_step_map(*, organization_id: int) -> dict[str, int]:
    rows = SourceBackupPipelineEntry.objects.filter(
        organization_id=organization_id,
        is_deleted=False,
    ).values("source_kind", "ref_id", "step")
    return {_selectable_key(str(row["source_kind"]), int(row["ref_id"])): int(row["step"]) for row in rows}


def attach_pipeline_steps(items: list[dict], *, pipeline_map: dict[str, int]) -> list[dict]:
    for item in items:
        item["pipeline_step"] = pipeline_map.get(str(item["id"]), PipelineStep.SOURCE_POOL)
    return items


def filter_items_by_pipeline_step(items: list[dict], step: int | None) -> list[dict]:
    if step is None or step not in PipelineStep.VALID:
        return items
    return [item for item in items if int(item.get("pipeline_step", PipelineStep.SOURCE_POOL)) == step]


def _source_exists(*, organization_id: int, source_kind: str, ref_id: int) -> bool:
    if source_kind == SelectableSourceKind.AGENT:
        return Node.objects.filter(
            organization_id=organization_id,
            role=NodeRole.AGENT,
            id=ref_id,
            is_deleted=False,
        ).exists()
    if source_kind == SelectableSourceKind.NAS:
        return SourceResource.objects.filter(
            organization_id=organization_id,
            resource_type=ResourceType.NAS,
            id=ref_id,
            is_deleted=False,
        ).exists()
    return False


def _backup_config_exists(*, organization_id: int, source_kind: str, ref_id: int) -> bool:
    from apps.protection.models import BackupConfig

    source_type = "agent" if source_kind == SelectableSourceKind.AGENT else source_kind
    return BackupConfig.objects.filter(
        organization_id=organization_id,
        source_type=source_type,
        source_ref_id=ref_id,
    ).exists()


def _upsert_pipeline_step(
    *,
    organization_id: int,
    source_kind: str,
    ref_id: int,
    step: int,
    current_step: int,
    allow_backwards: bool,
) -> str:
    key = _selectable_key(source_kind, ref_id)
    if step < current_step and not allow_backwards:
        raise ValueError(f"pipeline step cannot move backwards for {key}: {current_step} -> {step}")

    entry = SourceBackupPipelineEntry.all_objects.filter(
        organization_id=organization_id,
        source_kind=source_kind,
        ref_id=ref_id,
    ).first()
    if entry is None:
        SourceBackupPipelineEntry.objects.create(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
            step=step,
        )
    else:
        entry.step = step
        entry.is_deleted = False
        entry.deleted_at = None
        entry.updated_at = timezone.now()
        entry.save(update_fields=["step", "is_deleted", "deleted_at", "updated_at"])
    return key


def set_pipeline_steps(*, organization_id: int, ids: list[str], step: int) -> list[str]:
    if step not in PipelineStep.VALID:
        raise ValueError(f"invalid pipeline step: {step}")

    updated: list[str] = []
    for value in ids:
        parsed = parse_selectable_id(value)
        if not parsed:
            continue
        source_kind, ref_id = parsed
        if not _source_exists(organization_id=organization_id, source_kind=source_kind, ref_id=ref_id):
            continue
        key = _selectable_key(source_kind, ref_id)
        if step == PipelineStep.READY and not _backup_config_exists(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
        ):
            raise ValueError(f"backup config is required before moving {key} to step 3")

        entry = SourceBackupPipelineEntry.all_objects.filter(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
        ).first()
        current_step = (
            int(entry.step)
            if entry is not None and not entry.is_deleted
            else PipelineStep.SOURCE_POOL
        )
        updated.append(_upsert_pipeline_step(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
            step=step,
            current_step=current_step,
            allow_backwards=False,
        ))
    return updated


def force_set_pipeline_steps(*, organization_id: int, ids: list[str], step: int) -> list[str]:
    if step not in PipelineStep.VALID:
        raise ValueError(f"invalid pipeline step: {step}")

    updated: list[str] = []
    for value in ids:
        parsed = parse_selectable_id(value)
        if not parsed:
            continue
        source_kind, ref_id = parsed
        if not _source_exists(organization_id=organization_id, source_kind=source_kind, ref_id=ref_id):
            continue
        key = _selectable_key(source_kind, ref_id)
        if step == PipelineStep.READY and not _backup_config_exists(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
        ):
            raise ValueError(f"backup config is required before moving {key} to step 3")

        entry = SourceBackupPipelineEntry.all_objects.filter(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
        ).first()
        current_step = (
            int(entry.step)
            if entry is not None and not entry.is_deleted
            else PipelineStep.SOURCE_POOL
        )
        updated.append(_upsert_pipeline_step(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
            step=step,
            current_step=current_step,
            allow_backwards=True,
        ))
    return updated


def revert_backup_flow_sources(
    *,
    organization_id: int,
    ids: list[str],
    target_step: int,
) -> list[str]:
    """Move sources back to an earlier backup wizard step."""
    if target_step not in (PipelineStep.SOURCE_POOL, PipelineStep.CONFIG):
        raise ValueError("revert target_step must be 1 or 2")

    from apps.protection.services.backup_config import purge_backup_config_data_for_source

    updated: list[str] = []
    for value in ids:
        parsed = parse_selectable_id(value)
        if not parsed:
            continue
        source_kind, ref_id = parsed
        key = _selectable_key(source_kind, ref_id)
        if not _source_exists(organization_id=organization_id, source_kind=source_kind, ref_id=ref_id):
            continue

        if target_step == PipelineStep.CONFIG:
            source_type = "agent" if source_kind == SelectableSourceKind.AGENT else source_kind
            purge_backup_config_data_for_source(
                organization_id=organization_id,
                source_type=source_type,
                source_ref_id=ref_id,
            )
            updated.append(_upsert_pipeline_step(
                organization_id=organization_id,
                source_kind=source_kind,
                ref_id=ref_id,
                step=PipelineStep.CONFIG,
                current_step=PipelineStep.READY,
                allow_backwards=True,
            ))
        else:
            delete_pipeline_entry(
                organization_id=organization_id,
                source_kind=source_kind,
                ref_id=ref_id,
            )
            updated.append(key)
    return updated


def ensure_pipeline_entry(
    *,
    organization_id: int,
    source_kind: str,
    ref_id: int,
    step: int = PipelineStep.SOURCE_POOL,
) -> SourceBackupPipelineEntry | None:
    """Create the explicit pipeline row for a source without moving it backwards."""
    if step not in PipelineStep.VALID:
        raise ValueError(f"invalid pipeline step: {step}")
    if not _source_exists(organization_id=organization_id, source_kind=source_kind, ref_id=ref_id):
        return None

    entry = SourceBackupPipelineEntry.all_objects.filter(
        organization_id=organization_id,
        source_kind=source_kind,
        ref_id=ref_id,
    ).first()
    if entry is None:
        return SourceBackupPipelineEntry.objects.create(
            organization_id=organization_id,
            source_kind=source_kind,
            ref_id=ref_id,
            step=step,
        )

    current_step = int(entry.step) if not entry.is_deleted else PipelineStep.SOURCE_POOL
    if step < current_step:
        return entry
    entry.step = max(current_step, step)
    entry.is_deleted = False
    entry.deleted_at = None
    entry.updated_at = timezone.now()
    entry.save(update_fields=["step", "is_deleted", "deleted_at", "updated_at"])
    return entry


def delete_pipeline_entry(*, organization_id: int, source_kind: str, ref_id: int) -> None:
    for entry in SourceBackupPipelineEntry.all_objects.filter(
        organization_id=organization_id,
        source_kind=source_kind,
        ref_id=ref_id,
    ):
        if not entry.is_deleted:
            entry.soft_delete()


def purge_pipeline_entry(*, organization_id: int, source_kind: str, ref_id: int) -> None:
    """Hard-delete pipeline rows when the backing source identity is removed."""
    SourceBackupPipelineEntry.all_objects.filter(
        organization_id=organization_id,
        source_kind=source_kind,
        ref_id=ref_id,
    ).delete()
