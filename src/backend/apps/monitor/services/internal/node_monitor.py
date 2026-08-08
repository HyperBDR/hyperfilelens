"""Host helpers shared by ingest consumers (alerts/sources) and EE monitor reads."""

from __future__ import annotations

from apps.alert.constants import ResourceType
from apps.node.models.base import NodeRole

_ROLE_TO_RESOURCE_TYPE = {
    NodeRole.AGENT: ResourceType.AGENT_PROXY,
    NodeRole.PROXY: ResourceType.SYNC_PROXY,
    NodeRole.GATEWAY: ResourceType.GATEWAY,
}


def resource_type_for_role(role: str) -> str | None:
    try:
        return _ROLE_TO_RESOURCE_TYPE.get(NodeRole(role))
    except ValueError:
        return None
