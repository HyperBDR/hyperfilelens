"""Optional Sentry integration (no-op unless explicitly enabled with a DSN)."""

from __future__ import annotations

import logging
import os

from common.observability.context import (
    get_org_key,
    get_trace_id,
    get_user_id,
)

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in _TRUTHY


def _sample_rate(name: str, *, default: float = 0.0) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, min(1.0, value))


def init_sentry() -> None:
    """Initialize Sentry when ``SENTRY_ENABLED`` is true and ``SENTRY_DSN`` is set."""
    if not _env_bool("SENTRY_ENABLED"):
        return

    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        logger.debug("SENTRY_ENABLED is true but SENTRY_DSN is unset; skipping Sentry init")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
    except ImportError:
        logger.debug("sentry-sdk not installed; skipping Sentry init")
        return

    environment = (os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENV") or "").strip()
    release = (os.getenv("SENTRY_RELEASE") or os.getenv("APP_VERSION") or "").strip()

    traces_sample_rate = _sample_rate("SENTRY_TRACES_SAMPLE_RATE")
    profiles_sample_rate = _sample_rate(
        "SENTRY_PROFILES_SAMPLE_RATE",
        default=_sample_rate("SENTRY_PROFILING_SAMPLE_RATE"),
    )

    def _before_send(event, hint):  # noqa: ANN001, ARG001
        try:
            tags = event.get("tags") or {}
            rid = get_trace_id()
            if rid:
                tags["trace_id"] = rid
                tags["request_id"] = rid
            org_key = get_org_key()
            if org_key:
                tags["org_key"] = org_key
            user_id = get_user_id()
            if user_id:
                tags["user_id"] = user_id
            event["tags"] = tags
        except Exception:
            logger.debug("Failed to enrich Sentry event with request context")
        return event

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        environment=environment or None,
        release=release or None,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        send_default_pii=_env_bool("SENTRY_SEND_DEFAULT_PII"),
        before_send=_before_send,
    )
