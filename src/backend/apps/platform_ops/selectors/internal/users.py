"""Read-only user queries for Platform Ops."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, QuerySet

User = get_user_model()


def list_users(*, search: str = "") -> QuerySet:
    qs = User.objects.annotate(
        membership_count=Count("memberships", distinct=True),
    ).order_by("-date_joined", "id")
    term = (search or "").strip()
    if not term:
        return qs
    return qs.filter(
        Q(email__icontains=term)
        | Q(username__icontains=term)
        | Q(first_name__icontains=term)
        | Q(last_name__icontains=term),
    )


def get_user_detail(*, user_id: int):
    return (
        User.objects.filter(pk=user_id)
        .annotate(membership_count=Count("memberships", distinct=True))
        .prefetch_related("memberships__organization")
        .first()
    )
