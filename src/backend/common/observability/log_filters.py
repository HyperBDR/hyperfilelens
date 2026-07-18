from __future__ import annotations

import logging
import os
import socket

from common.observability.context import get_org_key, get_request_id, get_user_id
from common.observability.format import format_org_user, format_trace_id

_HOSTNAME = socket.gethostname() or "unknown"
_PID = os.getpid()
_SERVICE = "server-python"


class RequestContextFilter(logging.Filter):
    """
    Attach request-scoped and host fields to log records.

    Works even when no request context is set (e.g. startup, celery workers).
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        rid = get_request_id()
        org_key = get_org_key()
        user_id = get_user_id()

        record.hostname = _HOSTNAME
        record.process = _PID
        record.trace_id = format_trace_id(rid)
        record.org_user = format_org_user(org_key, user_id)
        record.service = _SERVICE

        # Backward-compatible aliases for filters and third-party integrations.
        record.request_id = rid
        record.org_key = org_key
        record.user_id = user_id
        return True
