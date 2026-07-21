"""Cloudflare Turnstile server-side verification."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_REQUEST_TIMEOUT = 5

_session: requests.Session | None = None


def _get_http_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def validate_turnstile(
    token: str,
    remote_ip: str | None = None,
    *,
    expected_action: str,
    expected_hostname: str,
) -> bool:
    """Verify a Turnstile token and bind it to the expected action and host."""
    from apps.platform_ops.services.internal.runtime_settings import turnstile_secret_key

    secret = turnstile_secret_key()
    if not secret:
        logger.error("[TURNSTILE] TURNSTILE_SECRET_KEY is not configured")
        return False

    token = (token or "").strip()
    if not token:
        return False

    payload: dict[str, str] = {
        "secret": secret,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = _get_http_session().post(
            TURNSTILE_VERIFY_URL,
            data=payload,
            timeout=TURNSTILE_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        logger.warning("[TURNSTILE] siteverify request failed: %s", exc)
        return False
    except ValueError:
        logger.warning("[TURNSTILE] siteverify returned invalid JSON")
        return False

    if not bool(result.get("success")):
        logger.info(
            "[TURNSTILE] verification failed: %s",
            result.get("error-codes"),
        )
        return False

    action = str(result.get("action") or "")
    hostname = str(result.get("hostname") or "").lower()
    if action != expected_action:
        logger.warning(
            "[TURNSTILE] action mismatch: expected=%s received=%s",
            expected_action,
            action or "-",
        )
        return False
    if hostname != expected_hostname.lower():
        logger.warning(
            "[TURNSTILE] hostname mismatch: expected=%s received=%s",
            expected_hostname,
            hostname or "-",
        )
        return False
    return True


def get_client_ip(request) -> str | None:
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR", "") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    remote = request.META.get("REMOTE_ADDR")
    return str(remote).strip() if remote else None
