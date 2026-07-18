"""Canonical agent data-directory paths shared by control plane and agent."""

from __future__ import annotations

DEFAULT_AGENT_DATA_DIR = "/var/lib/hyperfilelens-agent"

MOUNTS_DIR = "mounts"
MOUNT_REPOSITORIES_DIR = "repositories"
MOUNT_SOURCES_DIR = "sources"
MOUNT_CUSTOM_DIR = "custom"


def agent_data_dir(data_dir: str | None = None) -> str:
    root = (data_dir or DEFAULT_AGENT_DATA_DIR).strip().rstrip("/")
    return root or DEFAULT_AGENT_DATA_DIR


def agent_mounts_dir(data_dir: str | None = None) -> str:
    return f"{agent_data_dir(data_dir)}/{MOUNTS_DIR}"


def repository_mount_point(
    repository_id: int,
    *,
    node_id: int | None = None,
    data_dir: str | None = None,
) -> str:
    leaf = f"repo-{int(repository_id)}"
    if node_id is not None:
        leaf = f"{leaf}-node-{int(node_id)}"
    return f"{agent_mounts_dir(data_dir)}/{MOUNT_REPOSITORIES_DIR}/{leaf}"


def source_mount_point(resource_id: int, *, data_dir: str | None = None) -> str:
    return (
        f"{agent_mounts_dir(data_dir)}/{MOUNT_SOURCES_DIR}/source-{int(resource_id)}"
    )


def require_agent_mount_path(path: str, *, data_dir: str | None = None) -> str:
    cleaned = str(path or "").strip().rstrip("/")
    if not cleaned:
        raise ValueError("mount path is required")
    mounts_root = agent_mounts_dir(data_dir)
    if cleaned == mounts_root or cleaned.startswith(f"{mounts_root}/"):
        return cleaned
    raise ValueError(f"mount path must be under {mounts_root}/")
