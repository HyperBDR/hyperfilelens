"""
DRF exception handler to standardize error response body.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.errors import AppError, build_problem_details
from common.http.error_codes import (
    I18N_ERROR,
    I18N_FORBIDDEN,
    I18N_NOT_ACCEPTABLE,
    I18N_NOT_FOUND,
    I18N_SERVER_ERROR,
    I18N_UNAUTHORIZED,
    I18N_VALIDATION,
    ACCOUNT_DISABLED,
    INVALID_TOKEN,
    OTHER_DEVICE_LOGIN,
    PASSWORD_CHANGED,
    REFRESH_EXPIRED,
    TOKEN_BLACKLISTED,
    TOKEN_REUSED,
    map_http_status_to_error_code,
)


def _request_trace_id(context: dict[str, Any]) -> str:
    request = (context or {}).get("request")
    return str(getattr(request, "request_id", "") or "")


def _map_legacy_auth_code(error_code: str) -> str:
    """Preserve existing session-invalid codes consumed by the frontend."""
    legacy = {
        REFRESH_EXPIRED,
        TOKEN_BLACKLISTED,
        OTHER_DEVICE_LOGIN,
        PASSWORD_CHANGED,
        ACCOUNT_DISABLED,
        TOKEN_REUSED,
        INVALID_TOKEN,
    }
    if error_code in legacy:
        return error_code
    return error_code


def _validation_field_errors(data: Any) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        return []
    items: list[dict[str, str]] = []
    for field_name, messages in data.items():
        if field_name in {"detail", "non_field_errors"}:
            continue
        if isinstance(messages, list):
            message = str(messages[0]) if messages else ""
        else:
            message = str(messages)
        items.append(
            {
                "field": str(field_name),
                "code": "VALIDATION.FIELD_INVALID",
                "message": message,
            }
        )
    return items


def _problem_envelope(
    *,
    status_code: int,
    code: str,
    trace_id: str,
    retryable: bool = False,
    title: str = "",
    errors: list[dict[str, str]] | None = None,
    meta: dict[str, Any] | None = None,
    diagnostic: str = "",
) -> dict[str, Any]:
    detail = build_problem_details(
        AppError(
            code=code,
            status=status_code,
            retryable=retryable,
            title=title,
            field_errors=[],
            meta=meta or {},
            diagnostic=diagnostic,
        ),
        trace_id=trace_id,
    )
    if errors:
        detail["errors"] = errors
    return {
        "code": status_code,
        "message": "failed",
        "data": detail,
    }


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """
    Error payload (after CustomJSONRenderer):

      { code: <http_status>, message: "failed", data: <ProblemDetails> }
    """
    trace_id = _request_trace_id(context)

    if isinstance(exc, AppError):
        detail = build_problem_details(exc, trace_id=trace_id)
        return Response(
            {
                "code": exc.status,
                "message": "failed",
                "data": detail,
            },
            status=exc.status,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    status_code = int(getattr(response, "status_code", 500) or 500)
    data = response.data

    if isinstance(data, dict) and {"code", "message", "data"}.issubset(data.keys()):
        inner = data.get("data")
        if isinstance(inner, dict) and "code" in inner and "status" in inner:
            return response
        return response

    custom_error_code = None
    custom_message = None
    if isinstance(data, dict):
        if "error_code" in data:
            custom_error_code = data.pop("error_code")
        if "message" in data:
            custom_message = data.pop("message")

    error_code = map_http_status_to_error_code(status_code)
    if custom_error_code:
        error_code = _map_legacy_auth_code(str(custom_error_code))

    message = "failed"
    if custom_message:
        message = custom_message
    elif status_code == 406:
        message = str(_(I18N_NOT_ACCEPTABLE))
    elif status_code in (400, 422):
        message = str(_(I18N_VALIDATION))
    elif status_code == 401:
        message = str(_(I18N_UNAUTHORIZED))
    elif status_code == 403:
        message = str(_(I18N_FORBIDDEN))
    elif status_code == 404:
        message = str(_(I18N_NOT_FOUND))
    elif 500 <= status_code <= 599:
        message = str(_(I18N_SERVER_ERROR))
    else:
        message = str(_(I18N_ERROR))

    registry_code = error_code
    if status_code in (400, 422):
        registry_code = "VALIDATION.FAILED"
    elif status_code == 401:
        registry_code = _map_legacy_auth_code(str(error_code))
    elif status_code == 403:
        registry_code = "AUTH.FORBIDDEN"
    elif status_code == 404:
        registry_code = "RESOURCE.NOT_FOUND"
    elif 500 <= status_code <= 599:
        registry_code = "SERVER.INTERNAL_ERROR"

    field_errors = _validation_field_errors(data if isinstance(data, dict) else None)
    meta: dict[str, Any] = {}
    if isinstance(data, dict) and "detail" in data and data["detail"] not in (None, ""):
        meta["diagnostic"] = str(data["detail"])[:2000]
    if isinstance(data, dict):
        if isinstance(data.get("reasons"), list):
            meta["reasons"] = data["reasons"]
        if data.get("hint") not in (None, ""):
            meta["hint"] = str(data["hint"])[:2000]

    response.data = _problem_envelope(
        status_code=status_code,
        code=registry_code,
        trace_id=trace_id,
        retryable=status_code in {408, 429, 502, 503, 504},
        title=str(message),
        errors=field_errors,
        meta=meta,
        diagnostic=str(custom_message or message),
    )
    return response
