"""
Validate Agent ↔ control plane WebSocket credentials (query token vs enrollment rows).

Note: enrollment tokens stay active until ``expires_at`` (or manual revoke) and may
register multiple nodes. Legacy tokens deactivated after first use are still accepted
for WebSocket auth on nodes that enrolled with them.
"""

from __future__ import annotations

import secrets

from django.utils import timezone

from apps.node.models import Node, NodeToken


def validate_agent_ws_credentials(
    node_pk: int | None,
    token: str,
    *,
    expected_role: str | None = None,
    expected_gateway_scope: str | None = None,
) -> bool:
    """True when token matches the node organization and requested token bounds."""
    if not token or node_pk is None:
        return False
    node = Node.objects.filter(pk=int(node_pk)).first()
    if node is None:
        return False
    now = timezone.now()
    qs = NodeToken.objects.filter(organization_id=node.organization_id)
    for row in qs.only(
        "token",
        "role",
        "gateway_scope",
        "is_active",
        "expires_at",
        "used_at",
    ).iterator():
        if not secrets.compare_digest(row.token, token):
            continue
        if expected_role is not None and row.role != expected_role:
            continue
        if (
            expected_gateway_scope is not None
            and row.gateway_scope != expected_gateway_scope
        ):
            continue
        if row.is_active:
            if row.expires_at and row.expires_at <= now:
                continue
            return True
        if row.used_at is not None:
            return True
    return False
