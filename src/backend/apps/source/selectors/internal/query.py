from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.node.models.base import NodeRole
from apps.source.constants import ResourceType
from apps.source.models import SourceResource


def source_resources_queryset(
    *,
    organization_id: int,
    resource_type: str | None = None,
    status: str | None = None,
    mount_status: str | None = None,
    bound_node_id: int | None = None,
    bound_node_ids: list[int] | None = None,
    search: str | None = None,
    search_field: str | None = None,
) -> QuerySet[SourceResource]:
    qs = (
        SourceResource.objects.filter(organization_id=organization_id)
        .select_related("bound_node", "organization")
    )
    if resource_type:
        qs = qs.filter(resource_type=resource_type.strip())
    if status:
        qs = qs.filter(status=status.strip())
    if mount_status:
        qs = qs.filter(mount_status=mount_status.strip())
    if bound_node_ids:
        qs = qs.filter(bound_node_id__in=bound_node_ids)
    elif bound_node_id:
        qs = qs.filter(bound_node_id=bound_node_id)
    # Source hosts (local) are agent-only; hide legacy rows bound to proxy/gateway.
    qs = qs.filter(
        ~Q(resource_type=ResourceType.LOCAL)
        | Q(bound_node__isnull=True)
        | Q(bound_node__role=NodeRole.AGENT),
    )
    term = (search or "").strip()
    if term:
        field_q = _source_resource_field_search_q(search_field or "", term) if search_field else None
        qs = qs.filter(field_q or _source_resource_search_q(term))
    return qs.order_by("-created_at", "-id")


def _source_resource_search_q(term: str) -> Q:
    query = (
        Q(name__icontains=term)
        | Q(description__icontains=term)
        | Q(mount_point__icontains=term)
        | Q(status__icontains=term)
        | Q(bound_node__name__icontains=term)
        | Q(bound_node__ip_address__icontains=term)
    )
    for key in ("server", "share", "export_path", "endpoint", "bucket", "protocol", "root_path"):
        query |= Q(**{f"config__{key}__icontains": term})
    return query


def _source_resource_field_search_q(field: str, term: str) -> Q | None:
    normalized = (field or "").strip().lower()
    if normalized == "name":
        return Q(name__icontains=term)
    if normalized == "server":
        return (
            Q(config__server__icontains=term)
            | Q(config__endpoint__icontains=term)
            | Q(config__host__icontains=term)
        )
    if normalized in {"ip", "ip_address"}:
        return Q(bound_node__ip_address__icontains=term)
    return None


def source_resource_by_id(*, organization_id: int, resource_id: int) -> SourceResource | None:
    return (
        source_resources_queryset(organization_id=organization_id)
        .filter(id=resource_id)
        .first()
    )
