"""Read-only user queries for Platform Ops."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch, Q, QuerySet

from apps.iam.models import Membership

User = get_user_model()


def _with_account_context(qs: QuerySet) -> QuerySet:
    memberships = (
        Membership.objects.filter(is_active=True)
        .select_related("organization")
        .order_by("id")
    )
    return qs.select_related("profile").prefetch_related(
        Prefetch(
            "memberships",
            queryset=memberships,
            to_attr="platform_memberships",
        )
    )


def list_users(
    *,
    search: str = "",
    status: str = "",
    account_type: str = "",
) -> QuerySet:
    qs = User.objects.annotate(
        membership_count=Count(
            "memberships",
            filter=Q(memberships__is_active=True),
            distinct=True,
        ),
    )
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    elif status == "never_signed_in":
        qs = qs.filter(last_login__isnull=True)

    if account_type == "customer":
        qs = qs.filter(is_staff=False)
    elif account_type == "administrator":
        qs = qs.filter(is_staff=True)

    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(email__icontains=term)
            | Q(username__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(memberships__organization__key__icontains=term)
            | Q(memberships__organization__name__icontains=term),
        ).distinct()
    return _with_account_context(qs.order_by("-date_joined", "id"))


def user_account_stats() -> dict[str, int]:
    qs = User.objects.all()
    return {
        "total": qs.count(),
        "active": qs.filter(is_active=True).count(),
        "inactive": qs.filter(is_active=False).count(),
        "never_signed_in": qs.filter(last_login__isnull=True).count(),
    }


def get_user_detail(*, user_id: int):
    qs = (
        User.objects.filter(pk=user_id)
        .annotate(
            membership_count=Count(
                "memberships",
                filter=Q(memberships__is_active=True),
                distinct=True,
            )
        )
    )
    return _with_account_context(qs).first()
