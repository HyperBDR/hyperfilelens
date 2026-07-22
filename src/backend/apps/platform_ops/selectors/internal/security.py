"""Platform audit and staff activity selectors."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from apps.platform_ops.models import PlatformAuditLog

User = get_user_model()


def list_platform_audit_logs(
    *,
    search: str = "",
    action: str = "",
    result: str = "",
    org_key: str = "",
) -> QuerySet:
    from django.db.models import Q

    qs = PlatformAuditLog.objects.select_related("actor").order_by("-created_at", "-id")
    if action:
        qs = qs.filter(action=action)
    if result:
        qs = qs.filter(result=result)
    if org_key:
        qs = qs.filter(org_key=org_key)
    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(action__icontains=term)
            | Q(target_type__icontains=term)
            | Q(target_id__icontains=term)
            | Q(org_key__icontains=term)
            | Q(actor__email__icontains=term)
        )
    return qs


def list_staff_login_events(*, limit: int = 200) -> QuerySet:
    staff_ids = User.objects.filter(is_staff=True).values_list("id", flat=True)
    return (
        AuditLog.objects.filter(user_id__in=staff_ids, action=AuditAction.LOGIN)
        .select_related("organization", "user")
        .order_by("-created_at")[:limit]
    )
