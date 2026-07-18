"""Shared helpers for enrollment install and artifact download flows."""

from __future__ import annotations

import secrets
from urllib.parse import urlparse

from django.utils import timezone

from apps.iam.models import Organization
from apps.node.models import NodeToken


def enrollment_health(_request):
    from django.http import JsonResponse

    return JsonResponse({"app": "enrollment", "status": "ok"})


def agent_control_plane_ws_url(api_base: str) -> str:
    """Derive ws/wss URL for Agent WSS from HTTP API base."""
    base = (api_base or "").strip().rstrip("/")
    if not base:
        return ""
    parsed = urlparse(base)
    if not parsed.scheme or not parsed.netloc:
        return ""
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/ws/node/agent/"


def get_valid_enrollment_token(
    *,
    org: Organization,
    token: str,
    role: str,
) -> NodeToken | None:
    """Return an active, unexpired token row when ``token`` matches (timing-safe)."""
    if not token:
        return None
    now = timezone.now()
    for row in NodeToken.objects.filter(
        organization=org,
        role=role,
        is_active=True,
    ).only("id", "token", "expires_at"):
        if not secrets.compare_digest(row.token, token):
            continue
        if row.expires_at and row.expires_at <= now:
            continue
        return row
    return None


def token_usable_for_artifact_download(
    *,
    org: Organization,
    token: str,
    role: str,
) -> bool:
    """
    True when token may download signed agent artifacts.

    Active tokens are always allowed. Legacy one-time tokens that were deactivated
    after first use remain downloadable so existing install links can finish.
    """
    if get_valid_enrollment_token(org=org, token=token, role=role) is not None:
        return True
    if not token:
        return False
    for row in NodeToken.objects.filter(organization=org, role=role).only(
        "token",
        "used_at",
    ):
        if secrets.compare_digest(row.token, token) and row.used_at is not None:
            return True
    return False


def token_usable_for_bootstrap(
    *,
    org: Organization,
    token: str,
    role: str,
) -> bool:
    """
    True when bootstrap stub may be served (active token or legacy used link).

    Used links must still return a shell script so ``curl | bash`` can run ``hfl-enroll``
    and report idempotent success when the agent is already enrolled locally.
    """
    return token_usable_for_artifact_download(org=org, token=token, role=role)
