"""Shared helpers for agent / NodeTask log messages."""

from __future__ import annotations

import logging
from typing import Any

from common.observability.context import get_request_id

logger = logging.getLogger(__name__)


def _clip(value: Any, *, limit: int = 200) -> str:
    try:
        from apps.storage.services.internal.repository_secrets import scrub_secrets

        value = scrub_secrets(value)
    except Exception:
        pass
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def task_log_context(
    *,
    node_id: int | str | None,
    task_id: str | None = None,
    kind: str | None = None,
    correlation_type: str | None = None,
    correlation_id: str | None = None,
    trace_id: str | None = None,
    **extra: Any,
) -> str:
    """Build a single-line key=value suffix for agent task logs."""
    parts: list[str] = []
    if node_id is not None and str(node_id).strip():
        parts.append(f"node_id={node_id}")
    if task_id:
        parts.append(f"task_id={task_id}")
    if kind:
        parts.append(f"kind={kind}")
    if correlation_type:
        parts.append(f"correlation_type={correlation_type}")
    if correlation_id:
        parts.append(f"correlation_id={correlation_id}")
    rid = (trace_id or get_request_id() or "").strip()
    if rid:
        parts.append(f"trace_id={rid}")
    for key, value in extra.items():
        if value is None or value == "":
            continue
        if "password" in str(key).lower() or "secret" in str(key).lower():
            value = "******"
        parts.append(f"{key}={_clip(value)}")
    return " ".join(parts)


def agent_error_message(outcome: Any, default: str = "Agent task failed") -> str:
    """Extract a human-readable error from a sync/async agent task outcome."""
    def _clean(value: str) -> str:
        try:
            from apps.storage.services.internal.repository_secrets import scrub_secrets

            return str(scrub_secrets(value))
        except Exception:
            return value

    task = getattr(outcome, "task", None)
    last_error = str(getattr(task, "last_error", "") or "").strip()
    if last_error:
        return _clean(last_error)
    stream = getattr(outcome, "stream_message", None)
    if isinstance(stream, dict):
        for key in ("error", "message", "detail"):
            value = str(stream.get(key) or "").strip()
            if value:
                return _clean(value)
    result = getattr(outcome, "result", None)
    if isinstance(result, dict):
        for key in ("error", "stderr", "stdout", "detail", "message"):
            value = str(result.get(key) or "").strip()
            if value:
                return _clean(value)
    status = str(getattr(task, "status", "") or "").strip()
    if status:
        return f"{default} (status: {status})"
    return default


def _outcome_ok(outcome: Any) -> bool:
    if getattr(outcome, "timed_out", False):
        return False
    if hasattr(outcome, "ok"):
        return bool(outcome.ok)
    task = getattr(outcome, "task", None)
    return str(getattr(task, "status", "")).lower() in {"success", "succeeded", "ok"}


def log_agent_dispatch(
    operation: str,
    *,
    node_id: int | str,
    kind: str,
    correlation_type: str = "",
    correlation_id: str = "",
    **extra: Any,
) -> None:
    logger.info(
        "%s agent dispatch %s",
        operation,
        task_log_context(
            node_id=node_id,
            kind=kind,
            correlation_type=correlation_type,
            correlation_id=correlation_id,
            **extra,
        ),
    )


def log_agent_outcome(
    operation: str,
    *,
    outcome: Any,
    node_id: int | str,
    kind: str,
    correlation_type: str = "",
    correlation_id: str = "",
    **extra: Any,
) -> None:
    task = getattr(outcome, "task", None)
    ctx = task_log_context(
        node_id=node_id,
        task_id=str(getattr(task, "id", "") or ""),
        kind=kind,
        correlation_type=correlation_type,
        correlation_id=correlation_id,
        **extra,
    )
    if getattr(outcome, "timed_out", False):
        logger.warning("%s agent timed out %s", operation, ctx)
        return
    if _outcome_ok(outcome):
        logger.info(
            "%s agent ok %s task_status=%s",
            operation,
            ctx,
            getattr(task, "status", "-"),
        )
        return
    logger.warning(
        "%s agent failed %s task_status=%s error=%s",
        operation,
        ctx,
        getattr(task, "status", "-"),
        agent_error_message(outcome)[:500],
    )


def log_agent_exception(
    operation: str,
    *,
    node_id: int | str,
    kind: str,
    exc: BaseException,
    correlation_type: str = "",
    correlation_id: str = "",
    **extra: Any,
) -> None:
    logger.warning(
        "%s agent error %s error=%s",
        operation,
        task_log_context(
            node_id=node_id,
            kind=kind,
            correlation_type=correlation_type,
            correlation_id=correlation_id,
            **extra,
        ),
        _clip(exc),
    )
