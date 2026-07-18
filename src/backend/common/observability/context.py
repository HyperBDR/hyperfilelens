"""Request-scoped context variables for logging and error reporting."""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
org_key_var: ContextVar[str] = ContextVar("org_key", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


def get_request_id() -> str:
    return request_id_var.get() or ""


def get_org_key() -> str:
    return org_key_var.get() or ""


def get_user_id() -> str:
    return user_id_var.get() or ""


def get_trace_id() -> str:
    """Alias for request correlation id used in unified log lines."""
    return get_request_id()
