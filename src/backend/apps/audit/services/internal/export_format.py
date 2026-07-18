from __future__ import annotations

from datetime import UTC, datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime


def format_export_datetime(value: datetime | str | None) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            return value
        dt = parsed
    else:
        dt = value
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, UTC)
    dt_utc = dt.astimezone(UTC)
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_audit_export_row(row: dict) -> dict:
    formatted = dict(row)
    for key in ("timestamp", "created_at", "updated_at"):
        if key in formatted and formatted[key]:
            formatted[key] = format_export_datetime(formatted[key])
    return formatted
