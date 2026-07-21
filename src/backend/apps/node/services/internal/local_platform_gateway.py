"""Installer-managed local platform Gateway enrollment helpers."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.lens_bridge.models import LensGatewayLink
from apps.lens_bridge.services import platform_lens
from apps.node.models import NodeToken
from apps.node.models.base import NodeRole
from common.deploy.site import tenant_public_url

LOCAL_PLATFORM_GATEWAY_TOKEN_NOTE = "deploy:local-platform-gateway"
LOCAL_PLATFORM_GATEWAY_INSTALL_KEY = "local-platform-gateway"
LOCAL_PLATFORM_GATEWAY_METADATA = {
    "managed_by": "hfl-installer",
    "deployment_mode": "local-platform",
    "install_key": LOCAL_PLATFORM_GATEWAY_INSTALL_KEY,
}


def platform_gateway_api_base() -> str:
    """Return the configured tenant origin used by platform Data Gateways.

    Raises:
        ValueError: If ``FRONTEND_URL`` is not an absolute HTTP(S) origin.
    """
    api_base = tenant_public_url()
    parsed = urlsplit(api_base)
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError(
            "FRONTEND_URL must be an absolute HTTP(S) origin "
            "for Data Gateway enrollment."
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "FRONTEND_URL must be an absolute HTTP(S) origin "
            "for Data Gateway enrollment."
        )
    return api_base.rstrip("/")


@transaction.atomic
def ensure_local_platform_gateway_token() -> NodeToken:
    """Return a reusable enrollment token for the installer-managed Gateway."""
    org = platform_lens.get_or_create_platform_org()
    now = timezone.now()
    token = (
        NodeToken.objects.select_for_update()
        .filter(
            organization=org,
            role=NodeRole.GATEWAY,
            note=LOCAL_PLATFORM_GATEWAY_TOKEN_NOTE,
            gateway_scope=LensGatewayLink.GatewayScope.PLATFORM,
            is_active=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-created_at", "-id")
        .first()
    )
    if token is not None:
        return token
    return NodeToken.objects.create(
        organization=org,
        role=NodeRole.GATEWAY,
        note=LOCAL_PLATFORM_GATEWAY_TOKEN_NOTE,
        gateway_scope=LensGatewayLink.GatewayScope.PLATFORM,
    )


def is_local_platform_gateway_metadata(metadata: object) -> bool:
    """Return whether node metadata identifies the installer-managed Gateway."""
    return bool(
        isinstance(metadata, dict)
        and metadata.get("managed_by") == "hfl-installer"
        and metadata.get("deployment_mode") == "local-platform"
        and metadata.get("install_key") == LOCAL_PLATFORM_GATEWAY_INSTALL_KEY
    )


def registration_metadata(
    payload_metadata: object,
    *,
    token_note: str = "",
    existing_metadata: object = None,
) -> dict:
    """Preserve trusted installer ownership across Agent heartbeats."""
    metadata = dict(payload_metadata) if isinstance(payload_metadata, dict) else {}
    for key in LOCAL_PLATFORM_GATEWAY_METADATA:
        metadata.pop(key, None)
    installer_managed = (
        token_note == LOCAL_PLATFORM_GATEWAY_TOKEN_NOTE
        or is_local_platform_gateway_metadata(existing_metadata)
    )
    if installer_managed:
        metadata.update(LOCAL_PLATFORM_GATEWAY_METADATA)
    return metadata
