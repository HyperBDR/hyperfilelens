from __future__ import annotations

from typing import Any

from .app_error import AppError


DOCS_BASE = "https://docs.hyperfilelens.com/errors"


def problem_details_payload(
    *,
    code: str,
    status: int,
    trace_id: str = "",
    retryable: bool = False,
    title: str = "",
    errors: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": f"{DOCS_BASE}/{code.replace('.', '/')}",
        "title": title or code.replace(".", " ").replace("_", " ").title(),
        "status": int(status),
        "code": code,
        "retryable": bool(retryable),
        "errors": list(errors or []),
        "meta": dict(meta or {}),
    }
    if trace_id:
        payload["trace_id"] = trace_id
        payload["request_id"] = trace_id
    # Session / legacy clients read error_code from nested data.
    payload["error_code"] = code
    return payload


def build_problem_details(error: AppError, trace_id: str = "") -> dict[str, Any]:
    field_errors = [
        {
            "field": item.field,
            "code": item.code,
            "message": item.message,
        }
        for item in error.field_errors
    ]
    meta = dict(error.meta)
    if error.diagnostic:
        meta.setdefault("diagnostic", error.diagnostic[:2000])
    return problem_details_payload(
        code=error.code,
        status=error.status,
        trace_id=trace_id,
        retryable=error.retryable,
        title=error.title,
        errors=field_errors,
        meta=meta,
    )
