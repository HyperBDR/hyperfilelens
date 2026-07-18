"""Internal read queries for ``NodeToken``."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.iam.models import Organization
from apps.node.models import NodeToken


def node_tokens_queryset(
    *,
    org_key: str | None = None,
    organization_id: int | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> QuerySet[NodeToken]:
    queryset = NodeToken.objects.select_related("organization").all()
    if org_key:
        queryset = queryset.filter(organization__key=org_key)
    if organization_id is not None:
        queryset = queryset.filter(organization_id=organization_id)
    if role:
        queryset = queryset.filter(role=role)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-created_at", "-id")


def node_tokens_for_org(*, org: Organization) -> QuerySet[NodeToken]:
    return node_tokens_queryset(organization_id=org.id)
