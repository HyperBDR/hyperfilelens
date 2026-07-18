"""Ensure backup config directories have du-based size estimates before backup."""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError

from apps.node.services.interface import run_agent_task_sync
from apps.protection.models import BackupConfig, BackupConfigDirectory
from apps.protection.services.backup_task import ExecutionTarget, _resolve_execution_target
from apps.protection.models import BackupSourceSnapshot
from apps.source.services.internal.nas_share_path import to_mount_path

logger = logging.getLogger(__name__)

_PATH_SIZE_KIND = "path.size"
_PATH_SIZE_TIMEOUT_SECONDS = 300


class DirectorySizeEstimateError(ValidationError):
    """Raised when directory size cannot be estimated."""


def _agent_path_for_directory(
    *,
    directory: BackupConfigDirectory,
    execution_target: ExecutionTarget,
) -> str:
    path = str(directory.path or "").strip()
    if execution_target.source_type != "agent" and execution_target.root_path:
        return to_mount_path(execution_target.root_path, path)
    return path


def estimate_directory_size_bytes(
    *,
    node_id: int,
    path: str,
    path_type: str = "directory",
    organization_id: int,
    execution_target: ExecutionTarget,
) -> int:
    payload: dict[str, Any] = {
        "path": path,
        "path_type": path_type,
    }
    if execution_target.nas_payload:
        payload["nas"] = execution_target.nas_payload
    outcome = run_agent_task_sync(
        organization_id=organization_id,
        node_id=node_id,
        kind=_PATH_SIZE_KIND,
        payload=payload,
        wait_timeout_seconds=_PATH_SIZE_TIMEOUT_SECONDS,
    )
    if outcome.timed_out:
        raise DirectorySizeEstimateError(f"Path size estimation timed out for {path}")
    if not outcome.ok:
        error = str(outcome.task.last_error or "").strip()
        if not error and isinstance(outcome.stream_message, dict):
            error = str(outcome.stream_message.get("error") or outcome.stream_message.get("message") or "")
        if not error:
            error = "path size estimation failed"
        raise DirectorySizeEstimateError(error)
    result = outcome.result
    size_bytes = int(result.get("size_bytes") or 0)
    if size_bytes <= 0:
        raise DirectorySizeEstimateError(f"Path size estimate returned zero for {path}")
    return size_bytes


def ensure_backup_config_directory_estimates(
    *,
    organization_id: int,
    config: BackupConfig,
    source_type: str,
    source_ref_id: int,
) -> int:
    """Refresh missing estimates via Agent; return du_total. Raises if any path stays zero."""
    snapshot_stub = BackupSourceSnapshot(
        organization_id=organization_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
        backup_config_id=config.id,
    )
    execution_target = _resolve_execution_target(source_snapshot=snapshot_stub)
    node_id = int(execution_target.node.id)
    du_total = 0
    for directory in config.directories.all():
        current = max(0, int(directory.estimated_size_bytes or 0))
        if current <= 0:
            agent_path = _agent_path_for_directory(directory=directory, execution_target=execution_target)
            path_type = str(directory.path_type or "directory").strip().lower() or "directory"
            estimated = estimate_directory_size_bytes(
                node_id=node_id,
                path=agent_path,
                path_type=path_type,
                organization_id=organization_id,
                execution_target=execution_target,
            )
            directory.estimated_size_bytes = estimated
            directory.save(update_fields=["estimated_size_bytes", "updated_at"])
            current = estimated
            logger.info(
                "directory_size_estimated config_id=%s directory_id=%s path=%s size_bytes=%s",
                config.id,
                directory.id,
                agent_path,
                estimated,
            )
        du_total += current
    if du_total <= 0:
        raise DirectorySizeEstimateError("Backup cannot start without directory size estimates (du).")
    return du_total
