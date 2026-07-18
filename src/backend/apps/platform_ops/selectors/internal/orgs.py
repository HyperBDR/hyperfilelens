"""Read-only organization queries for Platform Ops."""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from apps.iam.models import Membership, Organization


def list_organizations(*, search: str = "") -> QuerySet:
    qs = (
        Organization.objects.annotate(
            member_count=Count(
                "memberships",
                filter=Q(memberships__is_active=True),
                distinct=True,
            ),
        )
        .order_by("-created_at", "id")
    )
    term = (search or "").strip()
    if not term:
        return qs
    return qs.filter(Q(key__icontains=term) | Q(name__icontains=term))


def get_organization_detail(*, org_id: int):
    return (
        Organization.objects.filter(pk=org_id)
        .annotate(
            member_count=Count(
                "memberships",
                filter=Q(memberships__is_active=True),
                distinct=True,
            ),
        )
        .prefetch_related("memberships__user")
        .first()
    )


def owner_email_for_org(org: Organization) -> str | None:
    owner = (
        Membership.objects.filter(
            organization=org,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        .select_related("user")
        .order_by("id")
        .first()
    )
    return owner.user.email if owner else None
