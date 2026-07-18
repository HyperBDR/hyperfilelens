"""Parse monitor API time range query parameters."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime


def resolve_time_range(
    *,
    hours_raw: str | None,
    start_at_raw: str | None,
    end_at_raw: str | None,
) -> tuple[datetime | None, datetime | None, dict | None]:
    """
    Return (since, until, error_payload).
    error_payload is None on success.
    """
    if start_at_raw or end_at_raw:
        if not start_at_raw or not end_at_raw:
            return (
                None,
                None,
                {
                    "error": "invalid_time_range",
                    "message": "start_at and end_at must be provided together.",
                },
            )
        since = _parse_datetime(start_at_raw)
        until = _parse_datetime(end_at_raw)
        if not since or not until:
            return (
                None,
                None,
                {
                    "error": "invalid_time_range",
                    "message": "start_at and end_at must be valid ISO datetime values.",
                },
            )
        if since > until:
            return (
                None,
                None,
                {
                    "error": "invalid_time_range",
                    "message": "start_at must be earlier than end_at.",
                },
            )
        return since, until, None

    try:
        hours = min(float(hours_raw or 24), 720)
    except (TypeError, ValueError):
        hours = 24.0
    hours = max(1 / 60, hours)
    until = timezone.now()
    since = until - timedelta(hours=hours)
    return since, until, None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value)
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed
