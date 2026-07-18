"""Provision and token management for SourceLens chat-only users."""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser

from apps.lens_bridge.models import LensSlUserLink
from apps.lens_bridge.services import sl_client

logger = logging.getLogger(__name__)

_USER_TOKEN_LOCK = threading.Lock()
_USER_TOKENS: dict[int, tuple[str, float]] = {}


def sl_username_for_hfl_user(user: AbstractBaseUser) -> str:
    return f"hfl-u-{user.pk}"


def _sl_password_for_hfl_user(user: AbstractBaseUser) -> str:
    """Derive a stable server-only password for an HFL-managed SL account."""
    digest = hmac.new(
        str(settings.SECRET_KEY).encode("utf-8"),
        f"sourcelens-chat-user:{user.pk}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"Hfl!{digest}"


def _find_remote_user(username: str) -> dict[str, Any] | None:
    page = 1
    page_size = 100
    while True:
        payload = sl_client.request_json(
            "GET",
            "/api/v1/management/users/",
            params={"page": page, "page_size": page_size},
        )
        if not isinstance(payload, dict):
            raise sl_client.LensBridgeError(
                "Unexpected SourceLens user list response."
            )
        rows = payload.get("results") or []
        if not isinstance(rows, list):
            raise sl_client.LensBridgeError(
                "Unexpected SourceLens user list results."
            )
        for row in rows:
            if isinstance(row, dict) and row.get("username") == username:
                return row
        total = int(payload.get("count") or 0)
        if not rows or page * page_size >= total:
            return None
        page += 1


def ensure_sl_chat_user(
    user: AbstractBaseUser,
    *,
    gateway_operator: bool = False,
) -> LensSlUserLink:
    """Idempotently provision an SL chat user for the given HFL user."""

    link = LensSlUserLink.objects.filter(hfl_user=user).first()
    if link is not None and link.provision_status == LensSlUserLink.ProvisionStatus.READY:
        if link.gateway_operator != gateway_operator:
            _provision_remote(user, link=link, gateway_operator=gateway_operator)
        return link

    if link is None:
        link = LensSlUserLink.objects.create(
            hfl_user=user,
            sl_user_id=0,
            sl_username=sl_username_for_hfl_user(user),
            gateway_operator=gateway_operator,
            provision_status=LensSlUserLink.ProvisionStatus.PENDING,
        )

    try:
        _provision_remote(user, link=link, gateway_operator=gateway_operator)
    except sl_client.LensBridgeError as exc:
        link.provision_status = LensSlUserLink.ProvisionStatus.ERROR
        link.last_error = str(exc.detail if hasattr(exc, "detail") else exc)[:2000]
        link.save(update_fields=["provision_status", "last_error", "updated_at"])
        raise

    return link


def _provision_remote(
    user: AbstractBaseUser,
    *,
    link: LensSlUserLink,
    gateway_operator: bool,
) -> None:
    username = sl_username_for_hfl_user(user)
    payload = _find_remote_user(username)
    if payload is None:
        try:
            payload = sl_client.request_json(
                "POST",
                "/api/v1/management/users/",
                json_body={
                    "username": username,
                    "email": "",
                    "password": _sl_password_for_hfl_user(user),
                    "is_staff": False,
                    "role_ids": [],
                    "preferred_platform": "workspace",
                },
            )
        except sl_client.LensBridgeError:
            payload = _find_remote_user(username)
            if payload is None:
                raise
    if not isinstance(payload, dict):
        raise sl_client.LensBridgeError("Unexpected provision response from SourceLens.")

    sl_user_id = int(payload.get("id") or 0)
    if sl_user_id <= 0:
        raise sl_client.LensBridgeError("SourceLens provision returned no user id.")

    link.sl_user_id = sl_user_id
    link.sl_username = str(payload.get("username") or link.sl_username)
    link.gateway_operator = gateway_operator
    link.provision_status = LensSlUserLink.ProvisionStatus.READY
    link.last_error = ""
    link.save(
        update_fields=[
            "sl_user_id",
            "sl_username",
            "gateway_operator",
            "provision_status",
            "last_error",
            "updated_at",
        ]
    )
    with _USER_TOKEN_LOCK:
        _USER_TOKENS.pop(user.pk, None)


def mint_sl_access_token(user: AbstractBaseUser) -> str:
    """Return a cached or freshly minted JWT for the user's SL chat account."""

    link = ensure_sl_chat_user(user)
    now = time.time()
    with _USER_TOKEN_LOCK:
        cached = _USER_TOKENS.get(user.pk)
        if cached and cached[1] > now:
            return cached[0]

    token = sl_client.login_user(
        username=link.sl_username,
        password=_sl_password_for_hfl_user(user),
    )
    with _USER_TOKEN_LOCK:
        _USER_TOKENS[user.pk] = (token, now + 25 * 60)
    return token


def invalidate_user_token(user_id: int) -> None:
    with _USER_TOKEN_LOCK:
        _USER_TOKENS.pop(user_id, None)


def enqueue_sl_chat_user_provision(*, user_id: int, gateway_operator: bool = False) -> None:
    """Best-effort async provisioning after registration."""

    from apps.lens_bridge.services.sync_queue import queue_sl_chat_user_provision

    queue_sl_chat_user_provision(user_id=user_id, gateway_operator=gateway_operator)
