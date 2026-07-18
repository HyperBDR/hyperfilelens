"""Normalize NAS SMB share and NFS export paths from user input."""

from __future__ import annotations

from typing import Any

from apps.source.constants import ResourceType


def _detect_nas_protocol(config: dict[str, Any]) -> str:
    explicit = str(config.get("protocol") or "").strip().lower()
    if explicit in ("smb", "cifs"):
        return "smb"
    if explicit == "nfs":
        return "nfs"
    if str(config.get("share") or "").strip():
        return "smb"
    if config.get("export_path"):
        return "nfs"
    return "nfs"


def _slash_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/")


def normalize_smb_share(value: str) -> str:
    """SMB/CIFS share name without a leading slash (share or share/subdir)."""
    raw = _slash_path(value)
    if not raw:
        return ""
    while raw.startswith("//"):
        raw = raw[1:]
    raw = raw.strip("/")
    parts = [part for part in raw.split("/") if part]
    return "/".join(parts)


def normalize_nfs_export_path(value: str) -> str:
    """NFS export path as an absolute POSIX path (/data or /export/backup)."""
    raw = _slash_path(value)
    if not raw:
        return ""
    parts = [part for part in raw.split("/") if part]
    if not parts:
        return "/"
    return "/" + "/".join(parts)


def normalize_nas_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize share/export_path fields on a NAS config dict (in place)."""
    cfg = dict(config or {})
    protocol = _detect_nas_protocol(cfg)
    if protocol == "smb":
        share = normalize_smb_share(str(cfg.get("share") or ""))
        if share:
            cfg["share"] = share
    else:
        export_raw = str(cfg.get("export_path") or cfg.get("path") or "")
        export_path = normalize_nfs_export_path(export_raw)
        if export_path:
            cfg["export_path"] = export_path
            if str(cfg.get("path") or "").strip() == export_raw.strip():
                cfg["path"] = export_path
    return cfg


def normalize_resource_config(resource_type: str, config: dict[str, Any] | None) -> dict[str, Any]:
    """Apply NAS path normalization for resource types that carry share/export paths."""
    cfg = dict(config or {})
    if resource_type == ResourceType.NAS:
        return normalize_nas_config(cfg)
    if resource_type == ResourceType.CIFS:
        share = normalize_smb_share(str(cfg.get("share") or ""))
        if share:
            cfg["share"] = share
        return cfg
    if resource_type == ResourceType.NFS:
        export_path = normalize_nfs_export_path(
            str(cfg.get("export_path") or cfg.get("path") or "")
        )
        if export_path:
            cfg["export_path"] = export_path
        return cfg
    return cfg
