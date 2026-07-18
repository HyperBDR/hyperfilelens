#!/usr/bin/env python3
"""Reject CJK characters from the public English-only repository."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CJK_PATTERN = re.compile(
    "["
    "\u1100-\u11ff"
    "\u3040-\u30ff"
    "\u3130-\u318f"
    "\u31f0-\u31ff"
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uac00-\ud7af"
    "\uf900-\ufaff"
    "\U00020000-\U0002fa1f"
    "]",
)
SKIPPED_DIRECTORY_NAMES = {
    ".git",
    ".agents",
    ".codex",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}
SKIPPED_TOP_LEVEL_DIRECTORIES = {"build", "data"}


def iter_public_files() -> Iterator[Path]:
    """Yield public repository files while excluding runtime and generated trees."""
    for path in REPOSITORY_ROOT.rglob("*"):
        relative_path = path.relative_to(REPOSITORY_ROOT)
        if (
            relative_path.parts
            and relative_path.parts[0] in SKIPPED_TOP_LEVEL_DIRECTORIES
        ):
            continue
        if any(part in SKIPPED_DIRECTORY_NAMES for part in path.parts):
            continue
        if path.is_file():
            yield path


def find_violations(path: Path) -> list[str]:
    """Return formatted CJK violations for a UTF-8 text file."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    violations: list[str] = []
    relative_path = path.relative_to(REPOSITORY_ROOT)
    for line_number, line in enumerate(content.splitlines(), start=1):
        for match in CJK_PATTERN.finditer(line):
            character = match.group(0)
            violations.append(
                f"{relative_path}:{line_number}:{match.start() + 1}: "
                f"{character!r} (U+{ord(character):04X})",
            )
    return violations


def main() -> int:
    """Scan public paths and contents and return a CI-friendly status code."""
    violations: list[str] = []
    for path in iter_public_files():
        relative_path = path.relative_to(REPOSITORY_ROOT)
        for match in CJK_PATTERN.finditer(str(relative_path)):
            character = match.group(0)
            violations.append(
                f"{relative_path}: path contains {character!r} "
                f"(U+{ord(character):04X})",
            )
        violations.extend(find_violations(path))
    if violations:
        print("CJK characters are not allowed in the English-only source release:")
        print("\n".join(violations))
        return 1

    print("English-only source check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
