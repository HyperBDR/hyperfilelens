"""Resolve or generate a request correlation ID."""

from __future__ import annotations

import uuid

from django.http import HttpRequest

_MAX_REQUEST_ID_LEN = 128


def get_request_id(request: HttpRequest) -> str:
    """Use ``X-Request-Id`` when present; otherwise generate a UUID hex id."""
    header = request.META.get("HTTP_X_REQUEST_ID") or ""
    header = str(header).strip()
    if header:
        return header[:_MAX_REQUEST_ID_LEN]
    return uuid.uuid4().hex
