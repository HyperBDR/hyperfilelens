"""Shared helpers for directory-browser composite IDs (agent:123, nas:456, proxy:7)."""

from __future__ import annotations


def parse_selectable_id(value: str) -> tuple[str, int] | None:
    raw = (value or "").strip()
    if ":" not in raw:
        return None
    kind, id_part = raw.split(":", 1)
    if kind not in ("agent", "nas", "proxy") or not id_part.isdigit():
        return None
    return kind, int(id_part)
