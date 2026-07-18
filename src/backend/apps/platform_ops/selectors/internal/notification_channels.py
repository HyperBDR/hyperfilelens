"""Cross-tenant notification channel overview for Platform Ops."""

from __future__ import annotations

from django.db.models import Count

from apps.notification.models import NotificationChannel


def list_platform_notification_channels() -> list[dict]:
    rows = []
    qs = (
        NotificationChannel.objects.select_related("organization")
        .annotate(delivery_count=Count("deliveries"))
        .order_by("organization__key", "name", "id")
    )
    for channel in qs:
        rows.append(
            {
                "id": channel.id,
                "organization_id": channel.organization_id,
                "organization_key": channel.organization.key,
                "organization_name": channel.organization.name,
                "name": channel.name,
                "channel_type": channel.channel_type,
                "is_active": channel.is_active,
                "delivery_count": channel.delivery_count,
                "updated_at": channel.updated_at,
            }
        )
    return rows
