from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError

from apps.node.models import Node
from apps.node.services.internal.node_registry import node_is_available_for_work
from apps.node.models.base import NodeRole
from apps.source.constants import ResourceType
from apps.source.models import SourceResource
from apps.source.services.internal.nas_agent import nas_payload_for_resource


@dataclass(frozen=True)
class ExecutionTarget:
    node: Node
    source_type: str
    source_ref_id: int
    root_path: str = ""
    nas_payload: dict[str, Any] | None = None


def resolve_source_execution_target(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> ExecutionTarget:
    normalized_type = str(source_type or "").strip().lower()
    normalized_ref_id = int(source_ref_id)
    if normalized_type == "agent":
        node = Node.objects.filter(
            organization_id=organization_id,
            id=normalized_ref_id,
            role=NodeRole.AGENT,
            is_deleted=False,
        ).first()
        if node is None:
            raise ValidationError({"source_ref_id": "Agent source not found."})
        if node.availability != Node.Availability.ONLINE:
            raise ValidationError({"source_ref_id": "Agent source is offline."})
        if not node_is_available_for_work(node):
            raise ValidationError({"source_ref_id": "Agent source is busy."})
        return ExecutionTarget(
            node=node,
            source_type="agent",
            source_ref_id=normalized_ref_id,
        )

    if normalized_type != "nas":
        raise ValidationError({"source_type": "Backup source type is not supported."})
    resource = (
        SourceResource.objects.filter(
            organization_id=organization_id,
            id=normalized_ref_id,
            resource_type=ResourceType.NAS,
            is_deleted=False,
        )
        .select_related("bound_node")
        .first()
    )
    if resource is None:
        raise ValidationError({"source_ref_id": "NAS source not found."})
    if resource.bound_node is None or resource.bound_node.role != NodeRole.PROXY:
        raise ValidationError({"source_ref_id": "NAS source is not bound to a proxy node."})
    if resource.availability != "online":
        raise ValidationError({"source_ref_id": "NAS source is offline."})
    if resource.bound_node.availability != Node.Availability.ONLINE:
        raise ValidationError({"source_ref_id": "Bound proxy node is offline."})
    if not node_is_available_for_work(resource.bound_node):
        raise ValidationError({"source_ref_id": "Bound proxy node is busy."})
    root_path = str(resource.effective_mount_point() or "").strip()
    if not root_path:
        raise ValidationError({"source_ref_id": "NAS source mount point is empty."})
    return ExecutionTarget(
        node=resource.bound_node,
        source_type="nas",
        source_ref_id=normalized_ref_id,
        root_path=root_path,
        nas_payload=nas_payload_for_resource(resource),
    )


__all__ = ["ExecutionTarget", "resolve_source_execution_target"]
