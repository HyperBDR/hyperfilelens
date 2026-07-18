"""Tests for UTC log formatters."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from common.observability.utc_formatter import UTCISO8601Formatter


def test_utc_iso8601_formatter_uses_zulu_suffix():
    formatter = UTCISO8601Formatter("%(asctime)s %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.created = datetime(2026, 5, 28, 3, 33, 5, 123000, tzinfo=timezone.utc).timestamp()
    record.msecs = 123

    rendered = formatter.format(record)

    assert "2026-05-28T03:33:05.123Z" in rendered
    assert "hello" in rendered
