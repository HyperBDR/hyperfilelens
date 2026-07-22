"""Read-only organization queries for Platform Ops."""

from __future__ import annotations

from django.db.models import Count, IntegerField, OuterRef, Prefetch, Q, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce

from apps.alert.constants import AlertStatus
from apps.iam.models import Membership, Organization
from apps.lens_bridge.services.platform_lens import PLATFORM_ORG_KEY
from apps.task.models import Task


def _failed_task_count_subquery() -> Subquery:
    rows = (
        Task.objects.filter(
            organization_id=OuterRef("pk"),
            status__in=[Task.Status.FAILED, Task.Status.TIMEOUT],
        )
        .values("organization_id")
        .annotate(total=Count("id"))
        .values("total")
    )
    return Subquery(rows, output_field=IntegerField())


def _with_account_context(qs: QuerySet) -> QuerySet:
    owners = (
        Membership.objects.filter(
            role=Membership.Role.OWNER,
            is_active=True,
        )
        .select_related("user")
        .order_by("id")
    )
    return qs.prefetch_related(
        Prefetch(
            "memberships",
            queryset=owners,
            to_attr="platform_owner_memberships",
        )
    )


def _with_operational_counts(qs: QuerySet) -> QuerySet:
    return qs.annotate(
        member_count=Count(
            "memberships",
            filter=Q(memberships__is_active=True),
            distinct=True,
        ),
        node_count=Count(
            "nodes",
            filter=Q(nodes__is_deleted=False),
            distinct=True,
        ),
        incident_count=Count(
            "alert_records",
            filter=Q(alert_records__status=AlertStatus.FIRING),
            distinct=True,
        ),
        failed_task_count=Coalesce(_failed_task_count_subquery(), Value(0)),
    )


def list_organizations(
    *,
    search: str = "",
    status: str = "",
    health: str = "",
) -> QuerySet:
    qs = _with_operational_counts(
        Organization.objects.exclude(key=PLATFORM_ORG_KEY),
    )
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    if health == "attention":
        qs = qs.filter(Q(incident_count__gt=0) | Q(failed_task_count__gt=0))
    elif health == "healthy":
        qs = qs.filter(incident_count=0, failed_task_count=0)

    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(key__icontains=term)
            | Q(name__icontains=term)
            | Q(
                memberships__role=Membership.Role.OWNER,
                memberships__is_active=True,
                memberships__user__email__icontains=term,
            )
        ).distinct()
    return _with_account_context(qs.order_by("-created_at", "id"))


def organization_account_stats() -> dict[str, int]:
    qs = Organization.objects.exclude(key=PLATFORM_ORG_KEY)
    return {
        "total": qs.count(),
        "active": qs.filter(is_active=True).count(),
        "inactive": qs.filter(is_active=False).count(),
        "with_incidents": qs.filter(
            alert_records__status=AlertStatus.FIRING,
        ).distinct().count(),
    }


def get_organization_detail(*, org_id: int):
    qs = _with_operational_counts(
        Organization.objects.filter(pk=org_id),
    )
    return _with_account_context(qs.prefetch_related("memberships__user")).first()


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
