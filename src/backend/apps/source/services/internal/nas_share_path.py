"""Share-relative path helpers for NAS backup source browsing and execution."""

from __future__ import annotations

import posixpath
from typing import Any

from apps.source.services.internal.nas_display import nfs_export_path, nas_protocol, smb_share


def share_root_label(*, resource_type: str, config: dict[str, Any]) -> str:
    """Human-readable label for the mounted share/export root."""

    cfg = config if isinstance(config, dict) else {}
    protocol = nas_protocol(cfg)
    if protocol == "nfs":
        label = nfs_export_path(resource_type=resource_type, config=cfg)
        if label:
            return label
    if protocol == "smb":
        label = smb_share(cfg)
        if label:
            return label
    return "/"


def normalize_share_relative_path(path: str) -> str:
    """Normalize a user-facing path relative to the share root."""

    value = str(path or "").strip()
    if not value or value == "/":
        return "/"
    if not value.startswith("/"):
        value = f"/{value}"
    normalized = posixpath.normpath(value)
    if normalized == ".":
        return "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def to_share_relative(mount_root: str, mount_path: str) -> str:
    """Convert a proxy mount path to a share-relative path."""

    clean_root = _clean_posix_path(mount_root).rstrip("/")
    clean_path = _clean_posix_path(mount_path).rstrip("/") or clean_root
    if not clean_root:
        return normalize_share_relative_path(clean_path)
    if clean_path == clean_root:
        return "/"
    prefix = f"{clean_root}/"
    if clean_path.startswith(prefix):
        return normalize_share_relative_path(clean_path[len(clean_root) :])
    return normalize_share_relative_path(clean_path)


def to_mount_path(mount_root: str, user_path: str) -> str:
    """Resolve a share-relative or legacy mount path to the proxy mount path."""

    clean_root = _clean_posix_path(mount_root).rstrip("/")
    if not clean_root:
        return _clean_posix_path(user_path)
    clean_user = str(user_path or "").strip()
    if not clean_user or clean_user == "/":
        return clean_root
    if _is_mount_subpath(clean_root, clean_user):
        return _clean_posix_path(clean_user).rstrip("/") or clean_root
    relative = normalize_share_relative_path(clean_user)
    if relative == "/":
        return clean_root
    return f"{clean_root}{relative}"


def normalize_user_share_path(
    *,
    mount_root: str,
    export_path: str,
    user_path: str,
) -> str:
    """Accept share-relative, export-prefixed, or mount-absolute NAS paths."""

    clean_user = str(user_path or "").strip()
    if not clean_user:
        return "/"
    clean_root = _clean_posix_path(mount_root).rstrip("/")
    if clean_root and _is_mount_subpath(clean_root, clean_user):
        return to_share_relative(clean_root, clean_user)
    export_clean = _clean_posix_path(export_path).rstrip("/")
    if export_clean:
        if clean_user == export_clean:
            return "/"
        export_prefix = f"{export_clean}/"
        if clean_user.startswith(export_prefix):
            return normalize_share_relative_path(clean_user[len(export_clean) :])
    return normalize_share_relative_path(clean_user)


def _clean_posix_path(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    return posixpath.normpath(value)


def _is_mount_subpath(root: str, path: str) -> bool:
    clean_root = _clean_posix_path(root).rstrip("/")
    clean_path = _clean_posix_path(path).rstrip("/") or clean_root
    if not clean_root or not clean_path:
        return False
    if clean_path == clean_root:
        return True
    return clean_path.startswith(f"{clean_root}/")
