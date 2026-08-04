"""Shared helpers for enrollment install and artifact download flows."""

from __future__ import annotations

import secrets
from urllib.parse import urlparse

from apps.iam.models import Organization
from apps.node.models import NodeToken
from apps.node.services.internal.enrollment_auth import (
    EnrollmentAuthorization,
    resolve_enrollment_authorization,
)


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
    """Return the token authorizing an enrollment token or active session."""
    authorization = resolve_enrollment_authorization(
        org=org,
        secret=token,
        role=role,
    )
    return authorization.token if authorization is not None else None


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
    return (
        resolve_artifact_download_authorization(
            org=org,
            token=token,
            role=role,
        )
        is not None
    )


def resolve_artifact_download_authorization(
    *,
    org: Organization,
    token: str,
    role: str,
) -> EnrollmentAuthorization | None:
    """Resolve active sessions/tokens and used legacy download links."""
    authorization = resolve_enrollment_authorization(
        org=org,
        secret=token,
        role=role,
    )
    if authorization is not None:
        return authorization
    if not token:
        return None
    for row in NodeToken.objects.filter(
        organization=org,
        role=role,
        enrollment_mode=NodeToken.EnrollmentMode.LEGACY,
    ).only(
        "token",
        "used_at",
    ):
        if secrets.compare_digest(row.token, token) and row.used_at is not None:
            return EnrollmentAuthorization(token=row)
    return None


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
