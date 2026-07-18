"""Published agent release artifacts under media/agent-releases/."""

from __future__ import annotations

import os
import re
from pathlib import Path

from django.conf import settings

from apps.node.models.base import NodeRole

AGENT_RELEASES_URL_PREFIX = "/media/agent-releases"
UBUNTU2404_LINUX_ROLES = frozenset({"proxy", "gateway"})
UPGRADEABLE_AGENT_ROLES = frozenset(
    {
        NodeRole.AGENT,
        NodeRole.PROXY,
        NodeRole.GATEWAY,
    },
)

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def agent_releases_root() -> Path:
    custom = os.getenv("AGENT_RELEASES_DIR", "").strip()
    if custom:
        return Path(custom)
    return Path(settings.MEDIA_ROOT) / "agent-releases"


def parse_semver(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").strip().lstrip("vV")
    match = _SEMVER_RE.match(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def semver_sort_key(name: str) -> tuple[int, ...]:
    parsed = parse_semver(name)
    if parsed is None:
        return (0, 0, 0)
    return parsed


def semver_compare(left: str, right: str) -> int:
    """Return -1 if left < right, 0 if equal, 1 if left > right."""
    left_parsed = parse_semver(left)
    right_parsed = parse_semver(right)
    if left_parsed is None or right_parsed is None:
        return 0
    if left_parsed < right_parsed:
        return -1
    if left_parsed > right_parsed:
        return 1
    return 0


def use_ubuntu2404_bundle(role: str | None, platform: str) -> bool:
    return platform == "linux" and (role or "") in UBUNTU2404_LINUX_ROLES


def dist_filename(
    version: str,
    platform: str,
    arch: str,
    *,
    ubuntu2404: bool = False,
) -> str:
    if ubuntu2404 and platform == "linux":
        return f"hfl-agent-{version}-linux-{arch}-ubuntu2404.tar.gz"
    ext = "zip" if platform == "windows" else "tar.gz"
    return f"hfl-agent-{version}-{platform}-{arch}.{ext}"


def version_has_dist(
    root: Path,
    version: str,
    platform: str,
    arch: str,
    *,
    role: str | None = None,
) -> bool:
    ubuntu2404 = use_ubuntu2404_bundle(role, platform)
    filename = dist_filename(version, platform, arch, ubuntu2404=ubuntu2404)
    return (root / version / filename).is_file()


def _dir_has_any_agent_archive(version_dir: Path) -> bool:
    if not version_dir.is_dir():
        return False
    for entry in version_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        if name.startswith("hfl-agent-") and (
            name.endswith(".tar.gz") or name.endswith(".zip")
        ):
            return True
    return False


def list_published_agent_versions() -> list[str]:
    root = agent_releases_root()
    if not root.is_dir():
        return []
    versions = [
        path.name
        for path in root.iterdir()
        if path.is_dir()
        and path.name not in ("dev",)
        and not path.name.startswith(".")
        and _dir_has_any_agent_archive(path)
    ]
    versions.sort(key=semver_sort_key, reverse=True)
    return versions


def latest_published_agent_version() -> str:
    """Console-facing agent release semver (newest under media/agent-releases/)."""
    preferred = os.getenv("AGENT_VERSION", "").strip()
    root = agent_releases_root()
    if preferred and _dir_has_any_agent_archive(root / preferred):
        return preferred
    published = list_published_agent_versions()
    if published:
        return published[0]
    return preferred or "0.0.0"


def resolve_agent_version(platform: str, arch: str, role: str | None = None) -> str:
    """Pick newest release dir that contains a dist archive for platform/arch."""
    root = agent_releases_root()
    preferred = os.getenv("AGENT_VERSION", "").strip()
    if preferred and version_has_dist(root, preferred, platform, arch, role=role):
        return preferred
    candidates = [
        path.name
        for path in root.iterdir()
        if path.is_dir()
        and path.name not in ("dev",)
        and not path.name.startswith(".")
        and version_has_dist(root, path.name, platform, arch, role=role)
    ]
    if not candidates:
        return preferred or latest_published_agent_version()
    if preferred and preferred in candidates:
        return preferred
    candidates.sort(key=semver_sort_key, reverse=True)
    return candidates[0]
