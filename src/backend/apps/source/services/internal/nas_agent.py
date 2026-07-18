"""Dispatch NAS mount/test/unmount tasks to bound Proxy agents."""

from __future__ import annotations

import logging
from typing import Any

from apps.node import agent_paths
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.agent_log import task_log_context
from apps.node.services.interface import run_agent_task_sync
from apps.source.constants import MountStatus, ResourceType
from apps.source.models import SourceResource
from apps.source.services.internal.nas_path_normalize import (
    normalize_nfs_export_path,
    normalize_smb_share,
)

logger = logging.getLogger(__name__)


class NASAgentError(RuntimeError):
    """Proxy agent failed to handle a NAS task."""


def nas_protocol(config: dict[str, Any]) -> str:
    explicit = str(config.get("protocol") or "").strip().lower()
    if explicit in ("smb", "cifs", "nfs"):
        return "smb" if explicit in ("smb", "cifs") else "nfs"
    if str(config.get("share") or "").strip():
        return "smb"
    if config.get("export_path"):
        return "nfs"
    return "nfs"


def build_nas_agent_payload(
    *,
    resource: SourceResource | None = None,
    resource_type: str = "",
    config: dict | None = None,
    credentials: dict | None = None,
    resource_id: int | None = None,
    mount_point: str = "",
) -> dict[str, Any]:
    cfg = dict(config or (resource.config if resource else {}) or {})
    creds = dict(credentials or (resource.credentials if resource else {}) or {})
    protocol = nas_protocol(cfg)
    resolved_mount_point = _resolve_nas_agent_mount_point(
        resource=resource,
        mount_point=mount_point,
        config=cfg,
    )
    payload: dict[str, Any] = {
        "resource_id": resource_id or (resource.id if resource else 0),
        "protocol": protocol,
        "server": str(cfg.get("server") or "").strip(),
        "mount_point": resolved_mount_point,
        "options": str(cfg.get("options") or "").strip(),
    }
    if protocol == "smb":
        payload["share"] = normalize_smb_share(str(cfg.get("share") or ""))
        payload["username"] = str(creds.get("username") or "").strip()
        payload["password"] = str(creds.get("password") or "")
        domain = str(creds.get("domain") or "").strip()
        if domain:
            payload["domain"] = domain
    else:
        payload["export_path"] = normalize_nfs_export_path(
            str(cfg.get("export_path") or cfg.get("path") or "")
        )
    storage_type = resource_type or (resource.resource_type if resource else ResourceType.NAS)
    payload["storage_type"] = storage_type
    return payload


def _resolve_nas_agent_mount_point(
    *,
    resource: SourceResource | None,
    mount_point: str,
    config: dict[str, Any],
) -> str:
    explicit = str(mount_point or "").strip()
    if explicit:
        return explicit
    if resource is not None:
        return resource.effective_mount_point()
    return str(config.get("path") or "").strip()


def explain_nas_mount_point_error(
    *,
    resource: SourceResource | None,
    agent_message: str,
    payload_mount_point: str = "",
) -> str:
    """Turn agent-side mount_point validation failures into actionable guidance."""
    msg = str(agent_message or "").strip()
    if "invalid mount_point" not in msg.lower():
        return msg

    mounts_root = agent_paths.agent_mounts_dir()
    if resource is not None:
        config_path = str((resource.config or {}).get("path") or "").strip()
        if config_path:
            try:
                agent_paths.require_agent_mount_path(config_path)
            except ValueError:
                return (
                    f'Mount directory "{config_path}" is outside the proxy agent mount root '
                    f"({mounts_root}/). Update it to a path under {mounts_root}/custom/, "
                    "for example "
                    f"{mounts_root}/custom/nfs-host_export."
                )

    sent = str(payload_mount_point or "").strip()
    if sent:
        return (
            f'Proxy agent rejected mount point "{sent}". '
            f"It must be under {mounts_root}/."
        )
    return f"Proxy agent rejected the mount path. Use a directory under {mounts_root}/."


_KNOWN_AGENT_WS_ERRORS: dict[str, str] = {
    "agent websocket is not routable": (
        "Proxy agent is offline or unreachable. "
        "Enable force delete to remove the source anyway, or wait until the proxy is online."
    ),
    "agent websocket is reconnecting": (
        "Proxy agent is reconnecting. Wait a moment and try again."
    ),
}


def _humanize_agent_ws_error(message: str) -> str:
    return _KNOWN_AGENT_WS_ERRORS.get(message.strip().lower(), message)


def _task_error_message(outcome) -> str:
    error = str(getattr(outcome.task, "last_error", "") or "").strip()
    if error:
        return _humanize_agent_ws_error(error)
    if isinstance(outcome.stream_message, dict):
        for key in ("error", "message", "detail"):
            value = str(outcome.stream_message.get(key) or "").strip()
            if value:
                return value
    status = str(getattr(outcome.task, "status", "") or "unknown")
    return f"Agent task failed (status: {status})."


def _validate_proxy_node(node: Node | None, *, resource: SourceResource | None = None) -> str | None:
    if node is None:
        return "No bound node configured. Please bind a proxy node first."
    if node.role != NodeRole.PROXY:
        return "NAS source must be bound to a proxy node."
    if node.status != Node.Status.ONLINE:
        return f'Bound node "{node.name}" is not online.'
    if resource is not None and resource.organization_id != node.organization_id:
        return "Bound node does not belong to this organization."
    return None


def dispatch_nas_agent_task(
    *,
    node: Node,
    kind: str,
    payload: dict[str, Any],
    correlation_type: str,
    correlation_id: str,
    wait_timeout_seconds: int = 120,
):
    nas = payload if kind.startswith("nas.") else payload.get("nas") or payload
    logger.info(
        "nas agent task dispatch %s protocol=%s server=%s resource_id=%s wait_seconds=%s",
        task_log_context(
            node_id=node.id,
            kind=kind,
            correlation_type=correlation_type,
            correlation_id=correlation_id,
        ),
        nas.get("protocol") if isinstance(nas, dict) else "-",
        nas.get("server") if isinstance(nas, dict) else "-",
        nas.get("resource_id") if isinstance(nas, dict) else "-",
        wait_timeout_seconds,
    )
    outcome = run_agent_task_sync(
        organization_id=node.organization_id,
        node_id=node.id,
        kind=kind,
        payload={"nas": payload, **payload},
        correlation_type=correlation_type,
        correlation_id=correlation_id,
        wait_timeout_seconds=wait_timeout_seconds,
    )
    ctx = task_log_context(
        node_id=node.id,
        task_id=str(getattr(outcome.task, "id", "")),
        kind=kind,
        correlation_type=correlation_type,
        correlation_id=correlation_id,
    )
    if outcome.timed_out:
        logger.warning("nas agent task timed out %s", ctx)
    elif outcome.ok:
        logger.info("nas agent task ok %s task_status=%s", ctx, outcome.task.status)
    else:
        logger.warning(
            "nas agent task failed %s task_status=%s error=%s",
            ctx,
            outcome.task.status,
            _task_error_message(outcome)[:500],
        )
    return outcome


def apply_mount_success(resource: SourceResource, result: dict[str, Any]) -> None:
    mount_point = resource.effective_mount_point()
    resource.mount_status = MountStatus.MOUNTED
    resource.mount_point = mount_point
    resource.mount_error = ""
    space = result.get("space_info") if isinstance(result.get("space_info"), dict) else {}
    if space:
        resource.total_size = int(space.get("total_bytes") or 0)
        resource.used_size = int(space.get("used_bytes") or 0)
        resource.free_size = int(space.get("free_bytes") or 0)
    resource.save(
        update_fields=[
            "mount_status",
            "mount_point",
            "mount_error",
            "total_size",
            "used_size",
            "free_size",
            "updated_at",
        ]
    )


def apply_mount_failure(resource: SourceResource, message: str) -> None:
    resource.mount_status = MountStatus.ERROR
    resource.mount_error = message[:2000]
    resource.save(update_fields=["mount_status", "mount_error", "updated_at"])


def apply_unmount_success(resource: SourceResource) -> None:
    resource.mount_status = MountStatus.UNMOUNTED
    resource.mount_error = ""
    resource.save(update_fields=["mount_status", "mount_error", "updated_at"])


def nas_payload_for_resource(resource: SourceResource) -> dict[str, Any]:
    return build_nas_agent_payload(resource=resource)
