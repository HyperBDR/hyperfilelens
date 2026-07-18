"""Shared helpers for Platform Ops API views."""

from __future__ import annotations


def safe_int(value, default: int, *, min_value: int = 1, max_value: int = 100) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, out))


def paginated(items, *, total: int, page: int, page_size: int) -> dict:
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": items,
    }
