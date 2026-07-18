"""HTTP client for SourceLens REST/SSE APIs (Bridge admin + per-user chat tokens)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Iterator
from urllib.parse import urljoin

import requests
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import APIException

from apps.lens_bridge import deploy

logger = logging.getLogger(__name__)

_ADMIN_TOKEN_LOCK = threading.Lock()
_ADMIN_ACCESS_TOKEN: str | None = None
_ADMIN_REFRESH_TOKEN: str | None = None
_ADMIN_ACCESS_EXPIRES_AT: float = 0.0


class LensBridgeError(APIException):
    status_code = 502
    default_detail = "SourceLens request failed."
    default_code = "lens_bridge_error"


class LensBridgeNotConfigured(LensBridgeError):
    status_code = 503
    default_detail = "SourceLens bridge is not configured."
    default_code = "lens_bridge_not_configured"


def _base_url() -> str:
    base = deploy.lens_base_url()
    if not base:
        raise LensBridgeNotConfigured()
    return base


def _ensure_credentials() -> None:
    if not deploy.lens_bridge_configured():
        raise LensBridgeNotConfigured()


def _unwrap_sl_body(body: Any) -> Any:
    """Unwrap SourceLens ``{code, message, data}`` envelope when present."""

    if isinstance(body, dict) and "data" in body and "code" in body:
        code = body.get("code")
        if code not in (0, "0", None):
            message = body.get("message") or body.get("detail") or "SourceLens request failed."
            raise LensBridgeError(str(message))
        return body.get("data")
    return body


def _extract_tokens(payload: dict[str, Any]) -> tuple[str, str | None]:
    access = payload.get("access") or payload.get("access_token")
    refresh = payload.get("refresh") or payload.get("refresh_token")
    if not access:
        raise LensBridgeError("SourceLens login response missing access token.")
    return str(access), str(refresh) if refresh else None


def _login() -> None:
    global _ADMIN_ACCESS_TOKEN, _ADMIN_REFRESH_TOKEN, _ADMIN_ACCESS_EXPIRES_AT
    _ensure_credentials()
    url = urljoin(_base_url() + "/", "api/v1/auth/login")
    response = requests.post(
        url,
        json={
            "username": deploy.lens_bridge_username(),
            "password": deploy.lens_bridge_password(),
        },
        timeout=30,
    )
    if response.status_code >= 400:
        logger.warning("SourceLens login failed: %s %s", response.status_code, response.text[:500])
        raise LensBridgeError("SourceLens authentication failed.")
    payload = _unwrap_sl_body(response.json())
    if not isinstance(payload, dict):
        raise LensBridgeError("SourceLens login returned unexpected payload.")
    access, refresh = _extract_tokens(payload)
    _ADMIN_ACCESS_TOKEN = access
    _ADMIN_REFRESH_TOKEN = refresh
    # JWT lifetime unknown; refresh proactively every 25 minutes.
    _ADMIN_ACCESS_EXPIRES_AT = time.time() + 25 * 60


def _refresh_access() -> None:
    global _ADMIN_ACCESS_TOKEN, _ADMIN_REFRESH_TOKEN, _ADMIN_ACCESS_EXPIRES_AT
    if not _ADMIN_REFRESH_TOKEN:
        _login()
        return
    url = urljoin(_base_url() + "/", "api/v1/auth/token/refresh")
    response = requests.post(url, json={"refresh": _ADMIN_REFRESH_TOKEN}, timeout=30)
    if response.status_code >= 400:
        logger.info("SourceLens token refresh failed; re-login.")
        _login()
        return
    payload = _unwrap_sl_body(response.json())
    if not isinstance(payload, dict):
        _login()
        return
    access, refresh = _extract_tokens(payload)
    _ADMIN_ACCESS_TOKEN = access
    if refresh:
        _ADMIN_REFRESH_TOKEN = refresh
    _ADMIN_ACCESS_EXPIRES_AT = time.time() + 25 * 60


def login_user(*, username: str, password: str) -> str:
    """Authenticate one ordinary SourceLens user and return its access token."""
    url = urljoin(_base_url() + "/", "api/v1/auth/login")
    response = requests.post(
        url,
        json={"username": username, "password": password},
        timeout=30,
    )
    if response.status_code >= 400:
        logger.warning(
            "SourceLens chat user login failed username=%s status=%s",
            username,
            response.status_code,
        )
        raise LensBridgeError("SourceLens chat user authentication failed.")
    try:
        payload = _unwrap_sl_body(response.json())
    except ValueError as exc:
        raise LensBridgeError(
            "SourceLens chat user login returned invalid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise LensBridgeError(
            "SourceLens chat user login returned unexpected payload."
        )
    access, _refresh = _extract_tokens(payload)
    return access


def _get_admin_access_token() -> str:
    global _ADMIN_ACCESS_TOKEN
    with _ADMIN_TOKEN_LOCK:
        if not _ADMIN_ACCESS_TOKEN or time.time() >= _ADMIN_ACCESS_EXPIRES_AT:
            if _ADMIN_REFRESH_TOKEN:
                _refresh_access()
            else:
                _login()
        if not _ADMIN_ACCESS_TOKEN:
            raise LensBridgeError("SourceLens access token unavailable.")
        return _ADMIN_ACCESS_TOKEN


def _get_access_token(*, hfl_user: AbstractBaseUser | None = None) -> str:
    if hfl_user is not None:
        from apps.lens_bridge.services.chat_user_provisioning import mint_sl_access_token

        return mint_sl_access_token(hfl_user)
    return _get_admin_access_token()


def _auth_headers(
    extra: dict[str, str] | None = None,
    *,
    hfl_user: AbstractBaseUser | None = None,
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {_get_access_token(hfl_user=hfl_user)}"}
    if extra:
        headers.update(extra)
    return headers


def _format_sl_error(body: Any) -> str:
    """Extract a readable message from SourceLens / DRF error payloads."""

    if not isinstance(body, dict):
        return str(body)

    non_field = body.get("non_field_errors")
    if isinstance(non_field, list) and non_field:
        return "; ".join(str(item) for item in non_field)

    detail = body.get("detail")
    if detail:
        return str(detail)

    message = body.get("message")
    if message:
        return str(message)

    for field, errors in body.items():
        if field in {"code", "type", "title", "errors", "meta", "data"}:
            continue
        if isinstance(errors, list) and errors:
            return f"{field}: {'; '.join(str(item) for item in errors)}"
        if isinstance(errors, dict):
            nested = _format_sl_error(errors)
            if nested:
                return f"{field}: {nested}"
    return str(body)


def _raise_for_response(response: requests.Response) -> Any:
    if response.status_code < 400:
        if not response.content:
            return None
        try:
            body = response.json()
        except ValueError:
            return response.text
        return _unwrap_sl_body(body)
    detail = response.text[:2000]
    try:
        body = response.json()
        try:
            unwrapped = _unwrap_sl_body(body)
        except LensBridgeError:
            unwrapped = body.get("data") if isinstance(body, dict) else body
        if isinstance(unwrapped, dict):
            detail = _format_sl_error(unwrapped)
        elif isinstance(body, dict):
            detail = _format_sl_error(body)
    except ValueError:
        body = detail
    exc = LensBridgeError(detail=str(detail))
    exc.status_code = response.status_code if 400 <= response.status_code < 600 else 502
    raise exc


def request_json(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = 60,
    hfl_user: AbstractBaseUser | None = None,
) -> Any:
    """Authenticated JSON request to SourceLens."""

    if not path.startswith("/"):
        path = f"/{path}"
    url = urljoin(_base_url() + "/", path.lstrip("/"))
    headers = _auth_headers({"Accept": "application/json"}, hfl_user=hfl_user)
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    response = requests.request(
        method.upper(),
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=timeout,
    )
    if response.status_code == 401:
        if hfl_user is not None:
            from apps.lens_bridge.services.chat_user_provisioning import invalidate_user_token

            invalidate_user_token(hfl_user.pk)
        else:
            with _ADMIN_TOKEN_LOCK:
                global _ADMIN_ACCESS_TOKEN
                _ADMIN_ACCESS_TOKEN = None
        headers = _auth_headers({"Accept": "application/json"}, hfl_user=hfl_user)
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        response = requests.request(
            method.upper(),
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout,
        )
    return _raise_for_response(response)


def stream_sse(
    path: str,
    *,
    timeout: int = 600,
    hfl_user: AbstractBaseUser | None = None,
) -> Iterator[bytes]:
    """Yield raw SSE bytes from SourceLens."""

    if not path.startswith("/"):
        path = f"/{path}"
    url = urljoin(_base_url() + "/", path.lstrip("/"))
    response = requests.get(
        url,
        headers=_auth_headers({"Accept": "text/event-stream"}, hfl_user=hfl_user),
        stream=True,
        timeout=timeout,
    )
    if response.status_code >= 400:
        _raise_for_response(response)

    def _iter() -> Iterator[bytes]:
        try:
            for chunk in response.iter_content(chunk_size=512):
                if chunk:
                    yield chunk
        finally:
            response.close()

    return _iter()


def ping() -> dict[str, Any]:
    """Lightweight connectivity check."""

    if not deploy.lens_bridge_configured():
        return {"configured": False, "reachable": False}
    try:
        health = requests.get(urljoin(_base_url() + "/", "health"), timeout=10)
        reachable = health.status_code == 200
    except requests.RequestException:
        reachable = False
    token_ok = False
    if reachable:
        try:
            _get_admin_access_token()
            token_ok = True
        except (LensBridgeError, ImproperlyConfigured):
            token_ok = False
    return {
        "configured": True,
        "reachable": reachable,
        "authenticated": token_ok,
        "base_url": deploy.lens_base_url(),
    }
