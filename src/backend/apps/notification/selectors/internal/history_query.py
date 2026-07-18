"""Notification log filtering (read path internals)."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.notification.models import NotificationLog


def filter_logs_queryset(
    queryset: QuerySet[NotificationLog],
    *,
    channel_id: str = "",
    status: str = "",
    notification_type: str = "",
    search: str = "",
    alert_record_ids: list | None = None,
) -> QuerySet[NotificationLog]:
    if channel_id:
        queryset = queryset.filter(channel_id=channel_id)
    if status:
        queryset = queryset.filter(status=status)
    if notification_type:
        queryset = queryset.filter(notification_type=notification_type)
    if alert_record_ids is not None:
        queryset = queryset.filter(alert_record_id__in=alert_record_ids)
    if search:
        queryset = queryset.filter(
            Q(event_type__icontains=search) | Q(error_message__icontains=search)
        )
    return queryset.order_by("-sent_at", "-id")
