"""Shared log field formatters for the unified log line prefix."""

from __future__ import annotations


def format_trace_id(raw: str) -> str:
    """Render trace id for logs: ``t-abc123`` or ``-`` when unset."""
    rid = (raw or "").strip()
    if not rid:
        return "-"
    if rid.startswith("t-"):
        return rid
    return f"t-{rid}"


def format_org_user(org_key: str, user_id: str) -> str:
    """Render org/user segment: ``org-default/u-42`` or ``-/-`` when unset."""
    org_part = f"org-{org_key.strip()}" if (org_key or "").strip() else "-"
    user_part = f"u-{user_id.strip()}" if (user_id or "").strip() else "-"
    return f"{org_part}/{user_part}"
