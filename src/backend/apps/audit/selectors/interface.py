"""
Audit read facade — cross-app callers should use this module only.
"""

from __future__ import annotations

from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.selectors.internal.audit_query import audit_logs_queryset


def list_audit_logs(
    *,
    org_key: str | None = None,
    action: str | None = None,
    correlation_id: str | None = None,
    request_id: str | None = None,
    target_type: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user_id: int | None = None,
    result: str | None = None,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    search_field: str | None = None,
    ip_address: str | None = None,
) -> QuerySet[AuditLog]:
    return audit_logs_queryset(
        org_key=org_key,
        action=action,
        correlation_id=correlation_id,
        request_id=request_id,
        target_type=target_type,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        result=result,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        search=search,
        search_field=search_field,
        ip_address=ip_address,
    )


def audit_statistics(*, org_key: str | None) -> dict:
    qs = audit_logs_queryset(org_key=org_key)
    total = qs.count()
    today = timezone.now().date()
    today_count = qs.filter(created_at__date=today).count()
    success = qs.filter(result="success").count()
    failure = qs.filter(result="failure").count()
    partial = qs.filter(result="partial").count()
    action_stats = {
        row["action"]: row["count"]
        for row in qs.values("action").annotate(count=Count("id")).order_by("-count")[:50]
    }
    resource_stats = {
        row["resource_type"]: row["count"]
        for row in qs.exclude(resource_type="")
        .values("resource_type")
        .annotate(count=Count("id"))
        .order_by("-count")[:50]
    }
    return {
        "total_count": total,
        "today_count": today_count,
        "success_rate": round((success / total) * 100, 2) if total else 0,
        "failure_count": failure,
        "partial_count": partial,
        "action_stats": action_stats,
        "resource_stats": resource_stats,
        "result_stats": {
            "success": success,
            "failure": failure,
            "partial": partial,
        },
    }
