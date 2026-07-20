#!/usr/bin/env python3
"""Safely add missing dotenv defaults and report deprecated keys."""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ENV_ASSIGNMENT_RE = re.compile(
    r"^[ \t]*(?P<key>[A-Z_][A-Z0-9_]*)=(?P<value>[^\r\n]*)$",
    flags=re.MULTILINE,
)

DEPRECATED_ENV_KEYS: dict[str, str] = {
    "HFL_REGISTRATION_ENABLED": "HFL_EMAIL_SIGNUP_ENABLED",
}


@dataclass(frozen=True)
class SyncResult:
    """Summary of a dotenv synchronization operation."""

    added_keys: tuple[str, ...]
    deprecated_keys: tuple[str, ...]


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def _assignments(text: str) -> dict[str, str]:
    return {
        match.group("key"): match.group("value")
        for match in ENV_ASSIGNMENT_RE.finditer(text)
    }


def _default_lines(text: str) -> list[tuple[str, str]]:
    defaults: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in ENV_ASSIGNMENT_RE.finditer(text):
        key = match.group("key")
        if key in seen:
            continue
        seen.add(key)
        defaults.append((key, match.group(0).lstrip(" \t")))
    return defaults


def _append_lines(text: str, lines: Sequence[str]) -> str:
    if not lines:
        return text

    newline = "\r\n" if "\r\n" in text else "\n"
    updated = text
    if updated and not updated.endswith(("\n", "\r")):
        updated += newline
    updated += newline.join(lines) + newline
    return updated


def _atomic_write(path: Path, content: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def sync_env_file(env_path: Path, example_path: Path) -> SyncResult:
    """Append missing example assignments without changing existing values.

    Deprecated assignments remain untouched and are returned for reporting.

    Args:
        env_path: Existing dotenv file to update.
        example_path: Dotenv example containing current default assignments.

    Returns:
        Keys added to the dotenv file and deprecated keys found in it.

    Raises:
        FileNotFoundError: If either input file does not exist.
    """
    env_text = _read_text(env_path)
    example_text = _read_text(example_path)
    existing = _assignments(env_text)

    missing = [
        (key, line)
        for key, line in _default_lines(example_text)
        if key not in existing
    ]
    if missing:
        _atomic_write(env_path, _append_lines(env_text, [line for _key, line in missing]))

    deprecated = tuple(key for key in DEPRECATED_ENV_KEYS if key in existing)
    return SyncResult(
        added_keys=tuple(key for key, _line in missing),
        deprecated_keys=deprecated,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add missing .env.example assignments without overwriting .env values.",
    )
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--example", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the dotenv synchronization command."""
    args = _build_parser().parse_args(argv)
    try:
        result = sync_env_file(args.env_file, args.example)
    except OSError as exc:
        print(f"ERROR: failed to synchronize environment file: {exc}", file=sys.stderr)
        return 1

    if result.added_keys:
        print(f"Added env keys: {', '.join(result.added_keys)}")
    for key in result.deprecated_keys:
        replacement = DEPRECATED_ENV_KEYS[key]
        print(
            f"Warning: {key} is deprecated and ignored; use {replacement} instead.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
