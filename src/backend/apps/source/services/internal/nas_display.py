"""Format NAS connection strings to match mount(8) source URIs."""

from __future__ import annotations

from typing import Any

from apps.source.constants import ResourceType
from apps.source.services.internal.nas_path_normalize import (
    normalize_nfs_export_path,
    normalize_smb_share,
)


def nas_protocol(config: dict[str, Any]) -> str | None:
    explicit = str(config.get("protocol") or "").strip().lower()
    if explicit in ("smb", "cifs"):
        return "smb"
    if explicit == "nfs":
        return "nfs"
    if str(config.get("share") or "").strip():
        return "smb"
    if config.get("export_path"):
        return "nfs"
    return None


def nfs_export_path(*, resource_type: str, config: dict[str, Any]) -> str:
    export_path = normalize_nfs_export_path(str(config.get("export_path") or ""))
    if export_path:
        return export_path
    if resource_type == ResourceType.NFS:
        return normalize_nfs_export_path(str(config.get("path") or ""))
    return ""


def smb_share(config: dict[str, Any]) -> str:
    return normalize_smb_share(str(config.get("share") or ""))


def nas_mount_source_uri(*, resource_type: str, config: dict[str, Any]) -> str:
    cfg = config or {}
    server = str(cfg.get("server") or "").strip()
    protocol = nas_protocol(cfg)
    if resource_type == ResourceType.CIFS:
        protocol = "smb"
    elif resource_type == ResourceType.NFS:
        protocol = "nfs"

    if protocol == "smb":
        share = smb_share(cfg)
        if server and share:
            return f"//{server}/{share}"
        return server or share or "—"

    if protocol == "nfs":
        export_path = nfs_export_path(resource_type=resource_type, config=cfg)
        if server and export_path:
            return f"{server}:{export_path}"
        return server or export_path or "—"

    return "—"


def connection_summary_for_resource(*, resource_type: str, config: dict[str, Any]) -> str:
    cfg = config or {}
    if resource_type == ResourceType.LOCAL:
        return str(cfg.get("root_path") or cfg.get("path") or "—").strip() or "—"
    if resource_type in (ResourceType.NAS, ResourceType.NFS, ResourceType.CIFS):
        return nas_mount_source_uri(resource_type=resource_type, config=cfg)
    if resource_type == ResourceType.S3:
        endpoint = str(cfg.get("endpoint") or "").strip()
        bucket = str(cfg.get("bucket") or "").strip()
        if endpoint and bucket:
            return f"{endpoint}/{bucket}"
        return endpoint or bucket or "—"
    return "—"
