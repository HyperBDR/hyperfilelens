"""
Channel layer fan-out helpers (reserved for future real-time delivery).

External WebSocket is owned by apps.node only (ws/node/agent/). Callers may
enqueue org/user groups here for when a push transport is wired; today there is
no browser WS consumer in notification.
"""

from __future__ import annotations

import hashlib
import logging
import re

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

_GROUP_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_GROUP_NAME_LENGTH = 99


def channel_group_name(prefix: str, value: str | int) -> str:
    clean_prefix = _GROUP_SAFE_CHARS_RE.sub("_", str(prefix or "").strip()) or "group"
    clean_value = _GROUP_SAFE_CHARS_RE.sub("_", str(value or "").strip()).strip("._-") or "default"
    group_name = f"{clean_prefix}.{clean_value}"
    if len(group_name) <= _MAX_GROUP_NAME_LENGTH:
        return group_name
    digest = hashlib.sha1(group_name.encode("utf-8")).hexdigest()[:12]
    keep = _MAX_GROUP_NAME_LENGTH - len(digest) - 1
    return f"{group_name[:keep]}.{digest}"


def _push_to_group(group_name: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": "push.event", "payload": payload},
        )
    except Exception:
        logger.exception("Failed to push notification event to channel group %s", group_name)


def push_to_user(user_id: int, payload: dict) -> None:
    _push_to_group(channel_group_name("user", int(user_id)), payload)


def push_to_org(org_key: str, payload: dict) -> None:
    org_key = str(org_key or "").strip()
    if not org_key:
        return
    _push_to_group(channel_group_name("org", org_key), payload)
