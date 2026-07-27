"""Trusted, single-use handoff for OAuth error messages."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone

from apps.iam.models import OAuthErrorEvent

logger = logging.getLogger(__name__)
OAUTH_ERROR_EVENT_TTL = timedelta(minutes=2)
MAX_EVENT_ID_LENGTH = 256


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_oauth_error_event(reason: str) -> str:
    """Persist a verified OAuth failure and return its unguessable bearer ID."""
    valid_reasons = OAuthErrorEvent.Reason.values
    normalized_reason = (
        reason if reason in valid_reasons else OAuthErrorEvent.Reason.OAUTH_FAILED
    )
    now = timezone.now()
    OAuthErrorEvent.objects.filter(expires_at__lte=now).delete()

    event_id = secrets.token_urlsafe(32)
    OAuthErrorEvent.objects.create(
        token_hash=_token_hash(event_id),
        reason=normalized_reason,
        expires_at=now + OAUTH_ERROR_EVENT_TTL,
    )
    return event_id


def build_oauth_error_redirect(frontend_url: str, reason: str) -> str:
    error_page = f"{frontend_url.rstrip('/')}/auth/oauth/error"
    try:
        event_id = create_oauth_error_event(reason)
    except Exception:
        logger.exception("Unable to persist OAuth error event")
        return error_page
    return f"{error_page}?event_id={quote(event_id, safe='')}"


def consume_oauth_error_event(event_id: object) -> str | None:
    """Atomically consume a valid event, returning ``None`` for every invalid state."""
    if not isinstance(event_id, str):
        return None
    normalized_id = event_id.strip()
    if not normalized_id or len(normalized_id) > MAX_EVENT_ID_LENGTH:
        return None

    with transaction.atomic():
        event = (
            OAuthErrorEvent.objects.select_for_update()
            .filter(token_hash=_token_hash(normalized_id))
            .first()
        )
        if event is None:
            return None

        reason = event.reason if event.expires_at > timezone.now() else None
        event.delete()
        return reason
