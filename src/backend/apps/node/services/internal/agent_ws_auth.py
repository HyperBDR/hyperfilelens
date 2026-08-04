"""Validate Agent ↔ control plane WebSocket credentials (query token vs enrollment rows).

Note: enrollment tokens stay active until ``expires_at`` (or manual revoke) and may
register multiple nodes. Legacy tokens are accepted only as a one-time bridge until
the node receives a long-lived NodeCredential.
"""

from __future__ import annotations

from apps.node.models import Node
from apps.node.services.internal.enrollment_auth import (
    legacy_enrollment_token_for_node,
    validate_node_credential,
)


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
    if validate_node_credential(node, token):
        if expected_role is not None and node.role != expected_role:
            return False
        return True
    return (
        legacy_enrollment_token_for_node(
            node,
            token,
            expected_role=expected_role,
            expected_gateway_scope=expected_gateway_scope,
        )
        is not None
    )
