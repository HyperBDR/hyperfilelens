#!/usr/bin/env python3
"""Report unique on-disk bytes by offline release component."""

from __future__ import annotations

import os
import pathlib
import sys
from collections import defaultdict


def category(relative: pathlib.PurePosixPath) -> str:
    value = relative.as_posix()
    if value.startswith(("images/10-", "images/11-", "images/12-", "sourcelens/")):
        return "Bundled SourceLens"
    if value.startswith("images/00-"):
        return "HFL images"
    if value.startswith(("images/01-", "images/02-")):
        return "PostgreSQL and Redis"
    if value.startswith("payload/media/gateway-bootstrap/docker-debs-"):
        return "Ubuntu Docker bundles"
    if value.startswith(("payload/media/agent-releases/", "payload/media/enroll-bootstrap/")):
        return "Agent artifacts"
    return "Other runtime files"


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} PACKAGE_ROOT ARCHIVE", file=sys.stderr)
        return 2
    root = pathlib.Path(sys.argv[1])
    archive = pathlib.Path(sys.argv[2])
    totals: dict[str, int] = defaultdict(int)
    seen: set[tuple[int, int]] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        totals[category(path.relative_to(root))] += stat.st_size

    archive_bytes = archive.stat().st_size
    lines = [
        "### Offline release size",
        "",
        f"Final archive: `{archive.name}` — {archive_bytes / 1_000_000_000:.3f} GB",
        "",
        "| Component | Unique size |",
        "| --- | ---: |",
    ]
    for name, size in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"| {name} | {size / (1024 * 1024):.1f} MiB |")
    report = "\n".join(lines) + "\n"
    print(report, end="")
    summary = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if summary:
        with pathlib.Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
