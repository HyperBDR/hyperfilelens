#!/usr/bin/env python3
"""Content fingerprints and atomic state storage for development workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


IGNORED_NAMES = {".DS_Store", ".git", "__pycache__"}


def iter_input_paths(root: Path, inputs: Iterable[str]) -> Iterable[Path]:
    """Yield deterministic files and symlinks for the requested repository paths."""
    for raw_path in sorted(set(inputs)):
        path = (root / raw_path).resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"input path escapes repository root: {raw_path}") from exc
        if not path.exists() and not path.is_symlink():
            yield path
            continue
        if path.is_file() or path.is_symlink():
            yield path
            continue
        for current_root, directory_names, file_names in os.walk(path):
            directory_names[:] = sorted(
                name for name in directory_names if name not in IGNORED_NAMES
            )
            for file_name in sorted(file_names):
                if file_name in IGNORED_NAMES or file_name.endswith((".pyc", ".pyo")):
                    continue
                yield Path(current_root) / file_name


def content_fingerprint(root: Path, paths: list[str], values: list[str]) -> str:
    """Return a stable SHA-256 over file paths, modes, contents, and explicit values."""
    digest = hashlib.sha256()
    for value in sorted(values):
        digest.update(b"value\0")
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    for path in iter_input_paths(root, paths):
        relative = path.relative_to(root).as_posix()
        digest.update(b"path\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if not path.exists() and not path.is_symlink():
            digest.update(b"missing\0")
            continue
        stat_result = path.lstat()
        digest.update(f"{stat_result.st_mode & 0o7777:o}".encode("ascii"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(path).encode("utf-8"))
        else:
            digest.update(b"file\0")
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def read_state(path: Path) -> dict[str, Any]:
    """Read a state document, treating a missing file as an empty state."""
    if not path.exists():
        return {"schema": 1, "components": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid cache state {path}: {exc}") from exc
    if data.get("schema") != 1 or not isinstance(data.get("components"), dict):
        raise ValueError(f"unsupported cache state schema in {path}")
    return data


def update_state(path: Path, key: str, fingerprint: str) -> None:
    """Atomically store a component fingerprint."""
    state = read_state(path)
    state["components"][key] = {
        "fingerprint": fingerprint,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(state, destination, indent=2, sort_keys=True)
            destination.write("\n")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def state_matches(path: Path, key: str, fingerprint: str) -> bool:
    """Return whether a stored component fingerprint matches."""
    try:
        state = read_state(path)
    except ValueError:
        return False
    component = state["components"].get(key)
    return isinstance(component, dict) and component.get("fingerprint") == fingerprint


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    fingerprint_parser = subparsers.add_parser("fingerprint")
    fingerprint_parser.add_argument("--root", type=Path, required=True)
    fingerprint_parser.add_argument("--path", action="append", default=[])
    fingerprint_parser.add_argument("--value", action="append", default=[])

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--state", type=Path, required=True)
    check_parser.add_argument("--key", required=True)
    check_parser.add_argument("--fingerprint", required=True)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--state", type=Path, required=True)
    update_parser.add_argument("--key", required=True)
    update_parser.add_argument("--fingerprint", required=True)
    return parser.parse_args()


def main() -> int:
    """Run the selected cache-state operation."""
    args = parse_args()
    if args.command == "fingerprint":
        root = args.root.resolve()
        print(content_fingerprint(root, args.path, args.value))
        return 0
    if args.command == "check":
        return 0 if state_matches(args.state, args.key, args.fingerprint) else 1
    if args.command == "update":
        update_state(args.state, args.key, args.fingerprint)
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
