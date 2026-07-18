"""Celery task trace injection and standard entry/exit logging."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, TypeVar

from common.observability.context import request_id_var

logger = logging.getLogger(__name__)

_celery_task_name: ContextVar[str] = ContextVar("celery_task_name", default="")

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def celery_trace(trace_id: str, *, task_name: str = ""):
    """Bind ``trace_id`` to logging context for the duration of a Celery task."""
    token = request_id_var.set(str(trace_id or "").strip())
    token_name = None
    if task_name:
        token_name = _celery_task_name.set(task_name)
    try:
        yield
    finally:
        if token_name is not None:
            _celery_task_name.reset(token_name)
        request_id_var.reset(token)


def logged_celery_task(*, name: str, trace_keys: tuple[str, ...] = ("task_uuid", "task_id")):
    """Decorator: inject trace id + INFO start/finish + exception logging."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            celery_request_id = ""
            if args and hasattr(args[0], "request"):
                celery_request_id = str(getattr(args[0].request, "id", "") or "")
            trace_id = ""
            for key in trace_keys:
                if key in kwargs and str(kwargs[key] or "").strip():
                    trace_id = str(kwargs[key]).strip()
                    break
            if not trace_id:
                trace_id = celery_request_id or name

            log_fields = " ".join(
                f"{key}={kwargs[key]}"
                for key in trace_keys
                if key in kwargs and kwargs[key] not in (None, "")
            )
            with celery_trace(trace_id, task_name=name):
                logger.info("celery task started name=%s %s", name, log_fields)
                try:
                    result = fn(*args, **kwargs)
                except Exception:
                    logger.exception("celery task failed name=%s %s", name, log_fields)
                    raise
                logger.info("celery task finished name=%s %s", name, log_fields)
                return result

        return wrapper  # type: ignore[return-value]

    return decorator
