"""Tests for unified log prefix helpers and filter."""

from __future__ import annotations

import logging

from common.observability.context import org_key_var, request_id_var, user_id_var
from common.observability.format import format_org_user, format_trace_id
from common.observability.log_filters import RequestContextFilter
from common.observability.utc_formatter import UTCISO8601Formatter


def test_format_trace_id_adds_prefix():
    assert format_trace_id("8a9d1c7f") == "t-8a9d1c7f"
    assert format_trace_id("t-8a9d1c7f") == "t-8a9d1c7f"
    assert format_trace_id("") == "-"


def test_format_org_user():
    assert format_org_user("888", "9527") == "org-888/u-9527"
    assert format_org_user("", "") == "-/-"


def test_unified_log_line_rendering():
    formatter = UTCISO8601Formatter(
        "[%(asctime)s] [%(levelname)s] [%(hostname)s:%(process)d] "
        "[%(trace_id)s] [%(org_user)s] "
        "[%(service)s(%(filename)s:%(lineno)d)] - %(message)s",
    )
    record = logging.LogRecord(
        name="apps.nas.api",
        level=logging.INFO,
        pathname="/app/apps/nas/api/views.py",
        lineno=68,
        msg="connection test failed: %s",
        args=({"err": "agent reported failure"},),
        exc_info=None,
    )
    record.created = 1782389101.25
    record.msecs = 250
    record.filename = "nas.py"

    token_rid = request_id_var.set("8a9d1c7f")
    token_org = org_key_var.set("888")
    token_user = user_id_var.set("9527")
    try:
        assert RequestContextFilter().filter(record) is True
        rendered = formatter.format(record)
    finally:
        request_id_var.reset(token_rid)
        org_key_var.reset(token_org)
        user_id_var.reset(token_user)

    assert rendered.startswith("[")
    assert "[INFO]" in rendered
    assert "[t-8a9d1c7f]" in rendered
    assert "[org-888/u-9527]" in rendered
    assert "[server-python(nas.py:68)]" in rendered
    assert "connection test failed" in rendered
