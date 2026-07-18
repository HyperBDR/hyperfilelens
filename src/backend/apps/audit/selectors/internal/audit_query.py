"""
Audit log list/detail queries.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.audit.models import AuditLog

_TIME_RANGE_DELTAS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _parse_bound(value: str, *, end_of_day: bool = False) -> datetime | None:
    if "T" not in value and " " not in value:
        parsed_date = parse_date(value)
        if parsed_date is not None:
            bound_time = time.max if end_of_day else time.min
            return timezone.make_aware(
                datetime.combine(parsed_date, bound_time),
                timezone.get_current_timezone(),
            )

    parsed_dt = parse_datetime(value)
    if parsed_dt is not None:
        if timezone.is_naive(parsed_dt):
            return timezone.make_aware(parsed_dt, timezone.get_current_timezone())
        return parsed_dt

    parsed_date = parse_date(value)
    if parsed_date is None:
        return None
    bound_time = time.max if end_of_day else time.min
    return timezone.make_aware(
        datetime.combine(parsed_date, bound_time),
        timezone.get_current_timezone(),
    )


def audit_logs_queryset(
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
    queryset = AuditLog.objects.select_related("organization", "user").all()
    if org_key:
        queryset = queryset.filter(organization__key=org_key)
    if action:
        queryset = queryset.filter(action=action)
    rid = (request_id or correlation_id or "").strip()
    if rid:
        queryset = queryset.filter(Q(correlation_id=rid) | Q(request_id=rid))
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    if resource_type:
        queryset = queryset.filter(resource_type=resource_type)
    if resource_id:
        queryset = queryset.filter(resource_id=resource_id)
    if user_id is not None:
        queryset = queryset.filter(user_id=user_id)
    if result:
        queryset = queryset.filter(result=result)
    if ip_address:
        queryset = queryset.filter(ip_address=ip_address)

    delta = _TIME_RANGE_DELTAS.get(time_range or "")
    if delta is not None:
        queryset = queryset.filter(created_at__gte=timezone.now() - delta)

    if start_date:
        parsed = _parse_bound(start_date)
        if parsed:
            queryset = queryset.filter(created_at__gte=parsed)
    if end_date:
        parsed = _parse_bound(end_date, end_of_day=True)
        if parsed:
            queryset = queryset.filter(created_at__lte=parsed)

    if search:
        term = search.strip()
        if search_field == "user":
            queryset = queryset.filter(
                Q(user_email__icontains=term)
                | Q(user_name__icontains=term)
                | Q(user__username__icontains=term)
            )
        elif search_field == "resource":
            queryset = queryset.filter(
                Q(resource_name__icontains=term) | Q(resource_id__icontains=term)
            )
        elif search_field == "ip":
            queryset = queryset.filter(ip_address__icontains=term)
        else:
            queryset = queryset.filter(
                Q(user_email__icontains=term)
                | Q(user_name__icontains=term)
                | Q(resource_name__icontains=term)
                | Q(resource_id__icontains=term)
                | Q(details__icontains=term)
                | Q(action__icontains=term)
            )

    return queryset.order_by("-created_at", "-id")
