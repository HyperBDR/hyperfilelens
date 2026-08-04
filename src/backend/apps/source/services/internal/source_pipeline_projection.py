"""Build the persisted read-model values for backup-selectable sources."""

from __future__ import annotations

from typing import Any

from apps.node.models.base import NodeRole
from apps.node.services.internal.node_naming import hostname_from_metadata
from apps.source.constants import Availability, PipelineTaskStatus, SelectableSourceKind


def _ip(node: Any | None) -> str:
    if node is None:
        return ""
    return str(node.ip_address or node.connection_ip_address or "").strip()


def _hostname(node: Any | None) -> str:
    if node is None:
        return ""
    return hostname_from_metadata(node.metadata) or str(node.name or "").strip()


def task_projection(task: Any | None) -> tuple[str, int | None]:
    if task is None:
        return PipelineTaskStatus.NONE, None
    status = str(task.status)
    return (
        PipelineTaskStatus.QUEUED if status == "pending" else status,
        int(task.id),
    )


def build_source_projection(
    *,
    source_kind: str,
    source: Any,
    backup_task: Any | None = None,
    restore_task: Any | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Return normalized Pipeline values and an optional inconsistency code."""
    backup_status, backup_id = task_projection(backup_task)
    restore_status, restore_id = task_projection(restore_task)
    if source_kind == SelectableSourceKind.AGENT:
        values = {
            "source_name": str(source.name or "").strip(),
            "source_hostname": _hostname(source),
            "source_ip": _ip(source),
            "source_status": str(source.status or ""),
            "source_availability": str(source.availability or Availability.OFFLINE),
            "last_backup_status": backup_status,
            "last_backup_task_id": backup_id,
            "last_restore_status": restore_status,
            "last_restore_task_id": restore_id,
        }
        return values, None

    proxy = getattr(source, "bound_node", None)
    valid_proxy = proxy is not None and not proxy.is_deleted and proxy.role == NodeRole.PROXY
    values = {
        "source_name": str(source.name or "").strip(),
        "source_hostname": _hostname(proxy) if valid_proxy else "",
        "source_ip": _ip(proxy) if valid_proxy else "",
        "source_status": str(source.status or ""),
        "source_availability": (
            str(source.availability or Availability.OFFLINE)
            if valid_proxy
            else Availability.OFFLINE
        ),
        "last_backup_status": backup_status,
        "last_backup_task_id": backup_id,
        "last_restore_status": restore_status,
        "last_restore_task_id": restore_id,
    }
    return values, None if valid_proxy else "nas_without_proxy"
