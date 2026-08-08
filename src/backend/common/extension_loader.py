"""Discover and load Host extensions from ``HFL_EXTENSIONS`` (Wave 5).

Runtime reads only local roots (or already-installed package layouts).
Prepare-stage git/path materialization belongs to ``stack.sh`` / CI via
``HFL_EXTENSION_SOURCES`` — this module never clones remotes.

Community builds leave ``HFL_EXTENSIONS`` empty.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOADED: bool = False
_EXTENSIONS: list["LoadedExtension"] = []


@dataclass(frozen=True)
class ExtensionManifest:
    id: str
    version: str = "0.0.0"
    requires_oss: str = ">=0.0.0"
    django_apps: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class LoadedExtension:
    root: Path
    backend: Path
    manifest: ExtensionManifest


def _env_str(name: str, default: str = "") -> str:
    import os

    raw = os.getenv(name)
    if raw is None:
        return default
    stripped = raw.strip()
    return stripped if stripped else default


def _parse_path_list(raw: str) -> list[Path]:
    items: list[Path] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        items.append(Path(piece).expanduser())
    return items


def _read_manifest(root: Path) -> ExtensionManifest:
    path = root / "extension.toml"
    if not path.is_file():
        # Allow legacy layouts without manifest during migration; invent id from dirname.
        return ExtensionManifest(id=root.name.replace("hyperfilelens-", "") or "extension")

    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    ext_id = str(data.get("id") or root.name).strip()
    if not ext_id:
        raise ValueError(f"extension.toml missing id: {path}")
    apps_raw = data.get("django_apps") or []
    if isinstance(apps_raw, str):
        django_apps = tuple(a.strip() for a in apps_raw.split(",") if a.strip())
    else:
        django_apps = tuple(str(a).strip() for a in apps_raw if str(a).strip())
    return ExtensionManifest(
        id=ext_id,
        version=str(data.get("version") or "0.0.0"),
        requires_oss=str(data.get("requires_oss") or ">=0.0.0"),
        django_apps=django_apps,
        raw=dict(data),
    )


def _looks_like_extension_root(root: Path) -> bool:
    backend = root / "src" / "backend"
    if not backend.is_dir():
        return False
    if (root / "extension.toml").is_file():
        return True
    # Accept tree that contributes Django apps under src/backend/apps
    return (backend / "apps").is_dir()


def extension_roots_from_env() -> list[Path]:
    """Parse ``HFL_EXTENSIONS`` into absolute roots (no discovery heuristics)."""
    roots: list[Path] = []
    for candidate in _parse_path_list(_env_str("HFL_EXTENSIONS")):
        resolved = candidate.resolve()
        if not _looks_like_extension_root(resolved):
            logger.error("HFL_EXTENSIONS entry is not an extension root: %s", resolved)
            continue
        roots.append(resolved)
    return roots


def bootstrap_extensions(*, backend_dir: Path | None = None) -> list[LoadedExtension]:
    """Append each extension ``src/backend`` to ``sys.path``.

    ``backend_dir`` is reserved for future Host-relative resolution; unused now.
    """
    global _LOADED, _EXTENSIONS
    _ = backend_dir  # Host-relative paths may be added later

    if _LOADED:
        return list(_EXTENSIONS)

    loaded: list[LoadedExtension] = []
    seen_ids: set[str] = set()

    for root in extension_roots_from_env():
        try:
            manifest = _read_manifest(root)
        except Exception:
            logger.exception("Failed to read extension manifest at %s", root)
            continue
        if manifest.id in seen_ids:
            logger.error("Duplicate extension id %r at %s — skipping", manifest.id, root)
            continue
        seen_ids.add(manifest.id)

        backend = (root / "src" / "backend").resolve()
        backend_str = str(backend)
        # Append after Host backend so shared package names prefer Host modules;
        # missing submodules resolve via pkgutil.extend_path into the plugin.
        if backend_str not in sys.path:
            sys.path.append(backend_str)

        item = LoadedExtension(root=root, backend=backend, manifest=manifest)
        loaded.append(item)
        logger.info("Extension %r v%s loaded from %s", manifest.id, manifest.version, root)

    _EXTENSIONS = loaded
    _LOADED = True
    return list(_EXTENSIONS)


def extensions_enabled() -> bool:
    if not _LOADED:
        bootstrap_extensions()
    return bool(_EXTENSIONS)


def loaded_extensions() -> list[LoadedExtension]:
    if not _LOADED:
        bootstrap_extensions()
    return list(_EXTENSIONS)


def extension_installed_apps() -> list[str]:
    """Extra Django apps declared by loaded extension manifests."""
    apps: list[str] = []
    seen: set[str] = set()
    for ext in loaded_extensions():
        for app in ext.manifest.django_apps:
            if app in seen:
                continue
            seen.add(app)
            apps.append(app)
    return apps
