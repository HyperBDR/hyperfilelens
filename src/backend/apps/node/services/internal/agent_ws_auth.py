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


def validate_agent_ws_credentials(node_pk: int | None, token: str) -> bool:
    """True when token matches an enrollment token row for the node's organization."""
    if not token or node_pk is None:
        return False
    node = Node.objects.filter(pk=int(node_pk)).first()
    if node is None:
        return False
    now = timezone.now()
    qs = NodeToken.objects.filter(organization_id=node.organization_id)
    for row in qs.only("token", "is_active", "expires_at", "used_at").iterator():
        if not secrets.compare_digest(row.token, token):
            continue
        if row.is_active:
            if row.expires_at and row.expires_at <= now:
                continue
            return True
        if row.used_at is not None:
            return True
    return False
