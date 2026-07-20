#!/usr/bin/env python3
"""Reject CJK characters from the public English-only repository."""

from __future__ import annotations

import os
import re
import subprocess
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


def iter_public_files() -> Iterator[Path]:
    """Yield tracked files and untracked files that Git does not ignore."""
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    for raw_relative_path in result.stdout.split(b"\0"):
        if not raw_relative_path:
            continue
        path = REPOSITORY_ROOT / os.fsdecode(raw_relative_path)
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
