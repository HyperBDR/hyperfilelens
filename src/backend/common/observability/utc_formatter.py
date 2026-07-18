"""UTC ISO 8601 formatters for application logs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone


class UTCISO8601Formatter(logging.Formatter):
    """Format log timestamps as UTC ISO 8601 (``2026-05-28T03:33:05.123Z``)."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return dt.strftime(datefmt)
        return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{int(record.msecs):03d}Z"
