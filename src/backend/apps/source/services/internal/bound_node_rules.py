"""Rules for which node roles may bind to a source resource type."""

from __future__ import annotations

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.source.constants import ResourceType


def validate_bound_node_role(*, resource_type: str, node: Node | None) -> None:
    if node is None:
        return
    if resource_type == ResourceType.LOCAL and node.role != NodeRole.AGENT:
        raise ValueError("Local source hosts must bind to an agent node.")


def bound_node_role_allowed(*, resource_type: str, node: Node | None) -> bool:
    if node is None:
        return True
    if resource_type == ResourceType.LOCAL:
        return node.role == NodeRole.AGENT
    return True
