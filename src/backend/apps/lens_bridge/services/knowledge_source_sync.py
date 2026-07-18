"""Unified async sync pipeline for Knowledge Sources (Add = first Sync, Sync = resume/rerun)."""

from __future__ import annotations

import logging
import time
from typing import Any

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import LensGatewayLink, LensKnowledgeSource
from apps.lens_bridge.services import gateway_readiness, ingest_policy, provisioning
from apps.node.models.node import Node
from apps.node.services.internal.node_workload import get_node_workload_blockers
from apps.protection.models import BackupSourceSnapshot, BackupSourceSnapshotDirectory
from apps.restore.models import RestoreRecord, RestoreRecordItem
from apps.restore.services import interface as restore_services
from apps.task.models import Task

logger = logging.getLogger(__name__)

SYNC_PHASES = (
    "prepare_workspace",
    "restore_snapshot",
    "push_assistant",
    "trigger_ingest",
    "finalize",
)

_PHASE_LABELS = {
    "prepare_workspace": "Preparing workspace on gateway…",
    "restore_snapshot": "Restoring snapshot data…",
    "push_assistant": "Syncing linked Assistant configuration…",
    "trigger_ingest": "Indexing and converting documents…",
    "finalize": "Finalizing…",
}

_RESTORE_WAIT_SECONDS = 6 * 3600
_RESTORE_POLL_SECONDS = 2.0
_TERMINAL_TASK_STATUSES = frozenset(
    {
        Task.Status.SUCCESS,
        Task.Status.FAILED,
        Task.Status.CANCELLED,
        Task.Status.TIMEOUT,
    }
)


class KnowledgeSourceSyncError(Exception):
    """Non-validation failure during knowledge source sync."""


def is_gateway_local_ks(ks: LensKnowledgeSource) -> bool:
    return not ks.backup_source_snapshot_id and not ks.backup_snapshot_directory_id


def scope_entries(ks: LensKnowledgeSource) -> list[dict[str, Any]]:
    rows = [
        item
        for item in (ks.source_scopes_json or [])
        if isinstance(item, dict) and str(item.get("source_path") or "").strip()
    ]
    if rows:
        return rows
    if ks.source_path:
        row: dict[str, Any] = {"source_path": ks.source_path.strip()}
        if ks.backup_snapshot_directory_id:
            row["backup_snapshot_directory_id"] = ks.backup_snapshot_directory_id
        return [row]
    return []


def _path_parts(path: str) -> list[str]:
    raw = str(path or "").strip().replace("\\", "/")
    if len(raw) >= 2 and raw[1] == ":":
        raw = raw[2:]
    return [part for part in raw.strip("/").split("/") if part not in ("", ".")]


def _common_path_parts(paths: list[str]) -> list[str]:
    parts_list = [_path_parts(path) for path in paths if str(path).strip()]
    if not parts_list:
        return []
    common: list[str] = []
    for index in range(min(len(parts) for parts in parts_list)):
        token = parts_list[0][index].lower()
        if any(parts[index].lower() != token for parts in parts_list):
            break
        common.append(parts_list[0][index])
    return common


def _relative_scope_path(*, ancestor_path: str, scope_path: str) -> str:
    ancestor = _path_parts(ancestor_path)
    child = _path_parts(scope_path)
    if len(child) < len(ancestor) or [part.lower() for part in child[: len(ancestor)]] != [
        part.lower() for part in ancestor
    ]:
        return "/".join(child)
    relative = child[len(ancestor) :]
    return "/".join(relative)


def _restore_selected_paths(*, directory_source_path: str, scope_path: str) -> list[str]:
    relative = _relative_scope_path(ancestor_path=directory_source_path, scope_path=scope_path)
    return [] if not relative else [relative]


def map_scope_to_workspace(*, workspace_root: str, scope_paths: list[str], scope_path: str) -> str:
    root = workspace_root.rstrip("/") or "/"
    normalized = [str(path).strip() for path in scope_paths if str(path).strip()]
    scope_parts = _path_parts(scope_path)
    if not normalized:
        rel = "/".join(scope_parts)
    else:
        common_parts = _common_path_parts(normalized)
        if scope_parts == common_parts:
            rel = scope_parts[-1] if scope_parts else "data"
        elif len(scope_parts) > len(common_parts) and [
            part.lower() for part in scope_parts[: len(common_parts)]
        ] == [part.lower() for part in common_parts]:
            rel = "/".join(scope_parts[len(common_parts) :])
        else:
            rel = "/".join(scope_parts)
    if not rel:
        rel = "data"
    return f"{root}/{rel}"


def indexed_dir_paths(ks: LensKnowledgeSource) -> list[str]:
    if is_gateway_local_ks(ks):
        return [str(item.get("source_path") or ks.source_path).strip() for item in scope_entries(ks)]
    workspace = (ks.workspace_path_on_lensnode or "").strip()
    if not workspace:
        raise KnowledgeSourceSyncError("Knowledge source workspace path is not set.")
    # SourceLens assistant create/update only accepts top-level LensNode dirs.
    return [workspace]


def resolve_snapshot_id_for_sync(*, ks: LensKnowledgeSource) -> int:
    if ks.linked_version_mode == LensKnowledgeSource.LinkedVersionMode.PINNED:
        pinned = ks.pinned_snapshot_id or ks.backup_source_snapshot_id
        if not pinned:
            raise KnowledgeSourceSyncError("Pinned snapshot is not configured.")
        return int(pinned)

    base_snapshot = BackupSourceSnapshot.objects.filter(
        organization_id=ks.organization_id,
        pk=ks.backup_source_snapshot_id,
        status__in=restore_services.RESTORABLE_SNAPSHOT_STATUSES,
    ).first()
    if base_snapshot is None:
        raise KnowledgeSourceSyncError("Configured backup snapshot is not restorable.")

    latest = (
        BackupSourceSnapshot.objects.filter(
            organization_id=ks.organization_id,
            source_type=base_snapshot.source_type,
            source_ref_id=base_snapshot.source_ref_id,
            backup_config_id=base_snapshot.backup_config_id,
            status__in=restore_services.RESTORABLE_SNAPSHOT_STATUSES,
        )
        .order_by("-finished_at", "-created_at", "-id")
        .first()
    )
    return int(latest.id if latest else base_snapshot.id)


def should_run_restore_phase(*, ks: LensKnowledgeSource, sync_state: dict[str, Any]) -> bool:
    if is_gateway_local_ks(ks):
        return False
    snapshot_id = resolve_snapshot_id_for_sync(ks=ks)
    used = sync_state.get("snapshot_id_used")
    completed = set(sync_state.get("completed_phases") or [])
    if "restore_snapshot" not in completed:
        return True
    if ks.linked_version_mode == LensKnowledgeSource.LinkedVersionMode.LATEST and used != snapshot_id:
        return True
    restore_record_id = sync_state.get("restore_record_id")
    if restore_record_id and not _restore_record_succeeded(
        record_id=int(restore_record_id),
        organization_id=ks.organization_id,
    ):
        return True
    pending_scopes = sync_state.get("restore_scope_status") or {}
    if any(status != "done" for status in pending_scopes.values()):
        return True
    return False


def enqueue_knowledge_source_sync(
    *,
    organization_id: int,
    knowledge_source_id: int,
    mode: str = "resume",
) -> None:
    from apps.lens_bridge.services.sync_queue import queue_knowledge_source_sync

    queue_knowledge_source_sync(
        organization_id=organization_id,
        knowledge_source_id=knowledge_source_id,
        mode=mode,
    )


def request_knowledge_source_sync(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    mode: str = "resume",
) -> LensKnowledgeSource:
    if ks.status == LensKnowledgeSource.Status.SYNCING:
        raise ValidationError({"status": "Knowledge source sync is already in progress."})

    blockers = get_node_workload_blockers(node=ks.gateway)
    if blockers:
        raise ValidationError(
            {
                "gateway": (
                    "Data gateway has active backup or restore tasks. "
                    "Wait for them to finish before syncing."
                )
            }
        )

    if ks.gateway.status != Node.Status.ONLINE:
        raise ValidationError({"gateway": "Data gateway must be online to sync."})

    from apps.node.services.internal.node_lifecycle import _active_lifecycle_task

    if _active_lifecycle_task(org=org, node=ks.gateway):
        raise ValidationError({"gateway": "Data gateway lifecycle operation is in progress."})

    gateway_link = provisioning.get_gateway_link(org, ks.gateway_id)
    if gateway_link.sidecar_status in {
        LensGatewayLink.SidecarStatus.UPGRADING,
        LensGatewayLink.SidecarStatus.REMOVING,
    }:
        raise ValidationError({"gateway": "Gateway AI engine is busy (upgrade or removal in progress)."})
    gateway_readiness.require_hfl_usable_gateway(gateway_link, field="gateway")

    sync_state = dict(ks.sync_state_json or {})
    if mode == "full":
        sync_state = {
            "mode": "full",
            "started_at": timezone.now().isoformat(),
            "completed_phases": [],
            "phase": "prepare_workspace",
            "restore_scope_status": {},
            "last_error": None,
        }
    else:
        sync_state.setdefault("mode", "resume")
        sync_state["started_at"] = timezone.now().isoformat()
        sync_state["phase"] = _resume_phase(sync_state)
        sync_state["last_error"] = None

    ks.status = LensKnowledgeSource.Status.SYNCING
    ks.status_detail = _PHASE_LABELS.get(str(sync_state.get("phase") or ""), "Syncing…")
    ks.sync_state_json = sync_state
    ks.save(update_fields=["status", "status_detail", "sync_state_json", "updated_at"])

    enqueue_knowledge_source_sync(
        organization_id=org.id,
        knowledge_source_id=ks.id,
        mode=mode,
    )
    return ks


def run_knowledge_source_sync(*, organization_id: int, knowledge_source_id: int) -> dict[str, Any]:
    from django.db import close_old_connections

    close_old_connections()
    ks = LensKnowledgeSource.objects.select_related("gateway").filter(
        organization_id=organization_id,
        pk=knowledge_source_id,
    ).first()
    if ks is None:
        raise KnowledgeSourceSyncError(f"Knowledge source {knowledge_source_id} not found.")

    org = Organization.objects.filter(pk=organization_id).first()
    if org is None:
        raise KnowledgeSourceSyncError(f"Organization {organization_id} not found.")

    try:
        return _run_sync_pipeline(org=org, ks=ks)
    except Exception as exc:
        logger.exception(
            "knowledge source sync failed ks_id=%s org_id=%s",
            knowledge_source_id,
            organization_id,
        )
        _mark_sync_error(ks=ks, message=str(exc))
        raise


def _run_sync_pipeline(*, org: Organization, ks: LensKnowledgeSource) -> dict[str, Any]:
    sync_state = dict(ks.sync_state_json or {})
    completed = set(sync_state.get("completed_phases") or [])

    if "prepare_workspace" not in completed:
        _run_phase_prepare_workspace(org=org, ks=ks, sync_state=sync_state)
        completed.add("prepare_workspace")
        sync_state["completed_phases"] = list(completed)
        ks.sync_state_json = sync_state
        ks.save(update_fields=["sync_state_json", "updated_at"])

    if should_run_restore_phase(ks=ks, sync_state=sync_state):
        _run_phase_restore_snapshot(org=org, ks=ks, sync_state=sync_state)
        completed.add("restore_snapshot")
    elif not is_gateway_local_ks(ks):
        completed.add("restore_snapshot")
    sync_state["completed_phases"] = list(completed)
    ks.sync_state_json = sync_state
    ks.save(update_fields=["sync_state_json", "updated_at"])

    if "push_assistant" not in completed:
        _run_phase_push_assistant(org=org, ks=ks, sync_state=sync_state)
        completed.add("push_assistant")
        sync_state["completed_phases"] = list(completed)
        ks.sync_state_json = sync_state
        ks.save(update_fields=["sync_state_json", "updated_at"])

    if "trigger_ingest" not in completed:
        _run_phase_trigger_ingest(org=org, ks=ks, sync_state=sync_state)
        completed.add("trigger_ingest")
        sync_state["completed_phases"] = list(completed)
        ks.sync_state_json = sync_state
        ks.save(update_fields=["sync_state_json", "updated_at"])

    _run_phase_finalize(org=org, ks=ks, sync_state=sync_state)
    completed.add("finalize")

    sync_state["completed_phases"] = list(SYNC_PHASES)
    sync_state["phase"] = "finalize"
    sync_state["last_sync_at"] = timezone.now().isoformat()
    sync_state["last_error"] = None
    ks.sync_state_json = sync_state
    ks.save(update_fields=["sync_state_json", "updated_at"])
    return {"knowledge_source_id": ks.id, "status": ks.status}


def _run_phase_prepare_workspace(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    sync_state: dict[str, Any],
) -> None:
    _update_sync_phase(ks=ks, sync_state=sync_state, phase="prepare_workspace")
    gateway = ks.gateway
    gateway_link = provisioning.get_gateway_link(org, gateway.id)

    if is_gateway_local_ks(ks):
        ks.workspace_path_on_lensnode = ks.source_path
        ks.mount_path_on_gateway = ks.source_path
        ks.save(update_fields=["workspace_path_on_lensnode", "mount_path_on_gateway", "updated_at"])
    else:
        workspace_path = ks.workspace_path_on_lensnode or provisioning.workspace_path_for_ks(
            org, gateway_link, ks.id
        )
        ks.workspace_path_on_lensnode = workspace_path
        ks.mount_path_on_gateway = workspace_path
        ks.save(update_fields=["workspace_path_on_lensnode", "mount_path_on_gateway", "updated_at"])
        provisioning.ensure_ks_workspace_on_gateway(
            org=org,
            gateway=gateway,
            gateway_link=gateway_link,
            workspace_path=workspace_path,
        )


def _run_phase_restore_snapshot(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    sync_state: dict[str, Any],
) -> None:
    _update_sync_phase(ks=ks, sync_state=sync_state, phase="restore_snapshot")
    snapshot_id = resolve_snapshot_id_for_sync(ks=ks)
    snapshot = BackupSourceSnapshot.objects.filter(
        organization_id=org.id,
        pk=snapshot_id,
        status__in=restore_services.RESTORABLE_SNAPSHOT_STATUSES,
    ).first()
    if snapshot is None:
        raise KnowledgeSourceSyncError("No restorable snapshot found for knowledge source.")

    workspace = ks.workspace_path_on_lensnode
    items: list[dict[str, Any]] = []
    restore_scope_status: dict[str, str] = dict(sync_state.get("restore_scope_status") or {})

    for index, entry in enumerate(scope_entries(ks)):
        key = str(index)
        if restore_scope_status.get(key) == "done":
            continue
        scope_path = str(entry.get("source_path") or "").strip()
        directory_id = entry.get("backup_snapshot_directory_id") or ks.backup_snapshot_directory_id
        if not directory_id:
            raise KnowledgeSourceSyncError(f"Index scope {index + 1} is missing snapshot directory id.")
        directory = BackupSourceSnapshotDirectory.objects.filter(
            organization_id=org.id,
            source_snapshot=snapshot,
            pk=int(directory_id),
        ).first()
        if directory is None:
            raise KnowledgeSourceSyncError(f"Snapshot directory {directory_id} not found for restore.")
        items.append(
            {
                "source_snapshot_directory_id": int(directory_id),
                "selected_paths": _restore_selected_paths(
                    directory_source_path=directory.source_path,
                    scope_path=scope_path,
                ),
                "target_path": workspace,
                "conflict_mode": "overwrite",
            }
        )
        restore_scope_status[key] = "pending"

    if not items:
        sync_state["snapshot_id_used"] = snapshot_id
        sync_state["restore_scope_status"] = restore_scope_status
        ks.sync_state_json = sync_state
        ks.save(update_fields=["sync_state_json", "updated_at"])
        return

    record = restore_services.create_manual_restore_record(
        organization_id=org.id,
        data={
            "source_type": snapshot.source_type,
            "source_ref_id": snapshot.source_ref_id,
            "target_type": "agent",
            "target_ref_id": ks.gateway_id,
            "source_snapshot_id": snapshot.id,
            "target_path": workspace,
            "scope": "paths",
            "conflict_mode": "overwrite",
            "items": items,
            "idempotency_key": f"ks-sync-{ks.id}-{snapshot_id}-{int(time.time())}",
        },
    )
    ks.last_restore_record_id = record.id
    sync_state["restore_record_id"] = record.id
    sync_state["snapshot_id_used"] = snapshot_id
    sync_state["restore_scope_status"] = restore_scope_status
    ks.sync_state_json = sync_state
    ks.save(update_fields=["last_restore_record_id", "sync_state_json", "updated_at"])

    _wait_for_restore_record(record_id=record.id, organization_id=org.id)

    for key in restore_scope_status:
        if restore_scope_status[key] != "done":
            restore_scope_status[key] = "done"
    sync_state["restore_scope_status"] = restore_scope_status
    ks.sync_state_json = sync_state
    ks.save(update_fields=["sync_state_json", "updated_at"])


def _run_phase_push_assistant(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    sync_state: dict[str, Any],
) -> None:
    _update_sync_phase(ks=ks, sync_state=sync_state, phase="push_assistant")
    gateway_link = provisioning.get_gateway_link(org, ks.gateway_id)
    lensnode_uuid = gateway_link.sl_lensnode_uuid
    if lensnode_uuid:
        for path in indexed_dir_paths(ks):
            provisioning.wait_for_lensnode_dir(lensnode_uuid=lensnode_uuid, path=path)
    provisioning.sync_linked_assistant_for_ks(
        org=org,
        ks=ks,
        gateway_link=gateway_link,
    )


def _run_phase_trigger_ingest(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    sync_state: dict[str, Any],
) -> None:
    _update_sync_phase(ks=ks, sync_state=sync_state, phase="trigger_ingest")
    provisioning.sync_assistant_ingest_settings(org=org, ks=ks)


def _run_phase_finalize(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    sync_state: dict[str, Any],
) -> None:
    _update_sync_phase(ks=ks, sync_state=sync_state, phase="finalize")
    ks.refresh_from_db()
    if not ks.scan_enabled:
        ks.status = LensKnowledgeSource.Status.PAUSED
        policy = ingest_policy.normalize_ingest_policy(ks.ingest_policy_json, org)
        ks.status_detail = ingest_policy.ingest_summary(policy)
        ks.save(update_fields=["status", "status_detail", "updated_at"])
        return

    if not provisioning.assistant_uuid_for_ks(ks):
        policy = ingest_policy.normalize_ingest_policy(ks.ingest_policy_json, org)
        ks.status = LensKnowledgeSource.Status.READY
        ks.status_detail = "Workspace ready. Create an Assistant to enable indexing."
        ks.save(update_fields=["status", "status_detail", "updated_at"])
        return

    provisioning.refresh_ks_status_from_sl(ks)
    ks.refresh_from_db()
    if ks.status == LensKnowledgeSource.Status.ERROR:
        return

    if _is_degraded(ks=ks, sync_state=sync_state):
        ks.status = LensKnowledgeSource.Status.DEGRADED
        ks.status_detail = "A newer backup snapshot is available. Sync to refresh."
        ks.save(update_fields=["status", "status_detail", "updated_at"])
        return

    policy = ingest_policy.normalize_ingest_policy(ks.ingest_policy_json, org)
    ks.status = LensKnowledgeSource.Status.READY
    ks.status_detail = ingest_policy.ingest_summary(policy)
    ks.save(update_fields=["status", "status_detail", "updated_at"])


def _is_degraded(*, ks: LensKnowledgeSource, sync_state: dict[str, Any]) -> bool:
    if is_gateway_local_ks(ks):
        return False
    if ks.linked_version_mode != LensKnowledgeSource.LinkedVersionMode.LATEST:
        return False
    try:
        latest_id = resolve_snapshot_id_for_sync(ks=ks)
    except KnowledgeSourceSyncError:
        return False
    used = sync_state.get("snapshot_id_used")
    return used is not None and int(used) != int(latest_id)


def _wait_for_restore_record(*, record_id: int, organization_id: int) -> None:
    deadline = time.monotonic() + _RESTORE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if _restore_record_succeeded(record_id=record_id, organization_id=organization_id):
            return
        if _restore_record_failed(record_id=record_id, organization_id=organization_id):
            record = RestoreRecord.objects.filter(pk=record_id, organization_id=organization_id).first()
            task = None
            if record is not None:
                task = Task.objects.filter(
                    organization_id=organization_id,
                    task_uuid=record.task_uuid,
                ).first()
            message = (task.error_message if task else None) or "Snapshot restore failed."
            raise KnowledgeSourceSyncError(message)
        time.sleep(_RESTORE_POLL_SECONDS)
    raise KnowledgeSourceSyncError("Snapshot restore timed out.")


def _restore_record_succeeded(*, record_id: int, organization_id: int) -> bool:
    record = RestoreRecord.objects.filter(pk=record_id, organization_id=organization_id).first()
    if record is None:
        return False
    statuses = list(record.items.values_list("status", flat=True))
    if not statuses:
        task = Task.objects.filter(organization_id=organization_id, task_uuid=record.task_uuid).first()
        return task is not None and task.status == Task.Status.SUCCESS
    return all(status == RestoreRecordItem.Status.SUCCESS for status in statuses)


def _restore_record_failed(*, record_id: int, organization_id: int) -> bool:
    record = RestoreRecord.objects.filter(pk=record_id, organization_id=organization_id).first()
    if record is None:
        return False
    statuses = list(record.items.values_list("status", flat=True))
    if any(status == RestoreRecordItem.Status.FAILED for status in statuses):
        return True
    task = Task.objects.filter(organization_id=organization_id, task_uuid=record.task_uuid).first()
    return task is not None and task.status in {
        Task.Status.FAILED,
        Task.Status.CANCELLED,
        Task.Status.TIMEOUT,
    }


def _resume_phase(sync_state: dict[str, Any]) -> str:
    completed = set(sync_state.get("completed_phases") or [])
    for phase in SYNC_PHASES:
        if phase not in completed:
            return phase
    return "prepare_workspace"


def _update_sync_phase(
    *,
    ks: LensKnowledgeSource,
    sync_state: dict[str, Any],
    phase: str,
) -> None:
    sync_state["phase"] = phase
    ks.status = LensKnowledgeSource.Status.SYNCING
    ks.status_detail = _PHASE_LABELS.get(phase, "Syncing…")
    ks.sync_state_json = sync_state
    ks.save(update_fields=["status", "status_detail", "sync_state_json", "updated_at"])


def _mark_sync_error(*, ks: LensKnowledgeSource, message: str) -> None:
    sync_state = dict(ks.sync_state_json or {})
    sync_state["last_error"] = message
    sync_state["phase"] = sync_state.get("phase") or "error"
    ks.status = LensKnowledgeSource.Status.ERROR
    ks.status_detail = message[:2000]
    ks.sync_state_json = sync_state
    ks.save(update_fields=["status", "status_detail", "sync_state_json", "updated_at"])


def maybe_refresh_degraded_status(*, ks: LensKnowledgeSource) -> LensKnowledgeSource:
    """Mark ready backup sources as degraded when a newer snapshot is available."""
    if ks.status != LensKnowledgeSource.Status.READY:
        return ks
    if is_gateway_local_ks(ks):
        return ks
    if ks.linked_version_mode != LensKnowledgeSource.LinkedVersionMode.LATEST:
        return ks
    sync_state = dict(ks.sync_state_json or {})
    used = sync_state.get("snapshot_id_used")
    if used is None:
        return ks
    try:
        latest_id = resolve_snapshot_id_for_sync(ks=ks)
    except KnowledgeSourceSyncError:
        return ks
    if int(latest_id) == int(used):
        return ks
    ks.status = LensKnowledgeSource.Status.DEGRADED
    ks.status_detail = "A newer backup snapshot is available. Sync to refresh."
    ks.save(update_fields=["status", "status_detail", "updated_at"])
    return ks


def prepare_new_knowledge_source(*, org: Organization, ks: LensKnowledgeSource) -> LensKnowledgeSource:
    """Allocate workspace paths and mark the row syncing before async pipeline starts."""
    gateway_link = provisioning.get_gateway_link(org, ks.gateway_id)
    ks.sl_lensnode_uuid = gateway_link.sl_lensnode_uuid
    if is_gateway_local_ks(ks):
        ks.workspace_path_on_lensnode = ks.source_path
        ks.mount_path_on_gateway = ks.source_path
    else:
        ks.workspace_path_on_lensnode = provisioning.workspace_path_for_ks(org, gateway_link, ks.id)
        ks.mount_path_on_gateway = ks.workspace_path_on_lensnode

    ks.status = LensKnowledgeSource.Status.SYNCING
    ks.status_detail = _PHASE_LABELS["prepare_workspace"]
    ks.sync_state_json = {
        "mode": "full",
        "phase": "prepare_workspace",
        "started_at": timezone.now().isoformat(),
        "completed_phases": [],
        "restore_scope_status": {},
        "last_error": None,
    }
    ks.save(
        update_fields=[
            "sl_lensnode_uuid",
            "workspace_path_on_lensnode",
            "mount_path_on_gateway",
            "status",
            "status_detail",
            "sync_state_json",
            "updated_at",
        ]
    )
    return ks
