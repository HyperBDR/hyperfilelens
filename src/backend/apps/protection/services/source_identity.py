from apps.node.models import Node
from apps.source.models import SourceResource


def resolve_source_display_name(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
    fallback: str = "",
) -> str:
    if source_type == "agent":
        name = Node.objects.filter(
            organization_id=organization_id,
            id=source_ref_id,
        ).values_list("name", flat=True).first()
    elif source_type == "nas":
        name = SourceResource.objects.filter(
            organization_id=organization_id,
            id=source_ref_id,
        ).values_list("name", flat=True).first()
    else:
        name = None
    return str(name or fallback).strip()
