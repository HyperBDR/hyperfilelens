"""Cross-tenant health queries for Platform Ops."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.alert.constants import AlertStatus
from apps.alert.models import AlertRecord
from apps.notification.constants import NotificationLogStatus
from apps.notification.models import NotificationDelivery, NotificationLog
from apps.node.services.internal.agent_release import agent_version_compare, latest_published_agent_version
from apps.platform_ops.selectors.internal.org_lookup import (
    organization_ids_for_key,
    organization_ids_matching,
)
from apps.task.models import Task


def list_platform_alerts(
    *,
    org_key: str = "",
    severity: str = "",
    status: str = "",
    search: str = "",
) -> QuerySet:
    qs = AlertRecord.objects.select_related("organization").order_by(
        "-last_triggered_at",
        "-created_at",
    )
    if org_key:
        qs = qs.filter(organization__key=org_key)
    if severity:
        qs = qs.filter(severity=severity)
    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(status__in=[AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED])
    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(title__icontains=term)
            | Q(message__icontains=term)
            | Q(resource_name__icontains=term)
            | Q(organization__key__icontains=term)
            | Q(organization__name__icontains=term)
        )
    return qs


def list_platform_tasks(
    *,
    org_key: str = "",
    status: str = "",
    task_type: str = "",
    search: str = "",
) -> QuerySet:
    qs = Task.objects.order_by("-finished_at", "-updated_at", "-id")
    if org_key:
        org_ids = organization_ids_for_key(org_key)
        qs = qs.filter(organization_id__in=org_ids or [-1])
    if status:
        qs = qs.filter(status=status)
    if task_type:
        qs = qs.filter(task_type=task_type)
    term = (search or "").strip()
    if term:
        org_ids = organization_ids_matching(term)
        qs = qs.filter(
            Q(display_name__icontains=term)
            | Q(error_message__icontains=term)
            | Q(organization_id__in=org_ids)
        )
    return qs


def platform_alert_stats() -> dict[str, int]:
    now = timezone.now()
    qs = AlertRecord.objects.all()
    return {
        "total": qs.count(),
        "firing": qs.filter(status=AlertStatus.FIRING).count(),
        "critical": qs.filter(status=AlertStatus.FIRING, severity="critical").count(),
        "acknowledged": qs.filter(status=AlertStatus.ACKNOWLEDGED).count(),
        "resolved": qs.filter(
            status=AlertStatus.RESOLVED,
            resolved_at__gte=now - timedelta(hours=24),
        ).count(),
    }


def platform_task_stats() -> dict[str, int | float]:
    since = timezone.now() - timedelta(hours=24)
    qs = Task.objects.all()
    terminal = qs.filter(finished_at__gte=since).filter(
        status__in=[Task.Status.SUCCESS, Task.Status.FAILED, Task.Status.TIMEOUT],
    )
    successful = terminal.filter(status=Task.Status.SUCCESS).count()
    terminal_count = terminal.count()
    return {
        "total": qs.count(),
        "running": qs.filter(status=Task.Status.RUNNING).count(),
        "failed": qs.filter(status=Task.Status.FAILED, finished_at__gte=since).count(),
        "timeout": qs.filter(status=Task.Status.TIMEOUT, finished_at__gte=since).count(),
        "success_rate": round((successful / terminal_count) * 100, 1) if terminal_count else 0,
    }


def list_platform_nodes(
    *,
    org_key: str = "",
    status: str = "",
    role: str = "",
    search: str = "",
) -> QuerySet:
    from apps.node.models import Node

    qs = Node.objects.select_related("organization").order_by("-updated_at", "-id")
    if org_key:
        qs = qs.filter(organization__key=org_key)
    if status:
        qs = qs.filter(status=status)
    if role:
        qs = qs.filter(role=role)
    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(name__icontains=term)
            | Q(ip_address__icontains=term)
            | Q(os_name__icontains=term)
            | Q(version__icontains=term)
            | Q(organization__key__icontains=term)
            | Q(organization__name__icontains=term)
        )
    return qs


def platform_node_stats() -> dict[str, int | str]:
    from apps.node.models import Node

    latest = latest_published_agent_version()
    versions = Node.objects.exclude(version="").values_list("version", flat=True)
    outdated = 0 if latest == "0.0.0" else sum(
        1 for version in versions if agent_version_compare(str(version), latest) < 0
    )
    return {
        "total": Node.objects.count(),
        "online": Node.objects.filter(status=Node.Status.ONLINE).count(),
        "offline": Node.objects.filter(status=Node.Status.OFFLINE).count(),
        "outdated": outdated,
        "latest_version": latest,
    }


def list_platform_notification_failures(*, org_key: str = "", search: str = "") -> QuerySet:
    qs = (
        NotificationLog.objects.filter(status=NotificationLogStatus.FAILED)
        .select_related("organization", "channel")
        .order_by("-sent_at", "-id")
    )
    if org_key:
        qs = qs.filter(organization__key=org_key)
    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(error_message__icontains=term)
            | Q(organization__key__icontains=term)
            | Q(organization__name__icontains=term)
            | Q(channel__name__icontains=term)
        )
    return qs


def list_platform_notification_deliveries(
    *,
    org_key: str = "",
    status: str = "",
    channel_type: str = "",
    event_type: str = "",
    search: str = "",
) -> QuerySet:
    qs = NotificationDelivery.objects.select_related("organization", "channel").order_by(
        "-created_at",
        "-id",
    )
    if org_key:
        qs = qs.filter(organization__key=org_key)
    if status:
        qs = qs.filter(status=status)
    if channel_type:
        qs = qs.filter(channel__channel_type=channel_type)
    if event_type:
        qs = qs.filter(event_type=event_type)
    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(event_type__icontains=term)
            | Q(error__icontains=term)
            | Q(channel__name__icontains=term)
            | Q(organization__key__icontains=term)
            | Q(organization__name__icontains=term)
        )
    return qs


def platform_notification_stats() -> dict[str, int | float]:
    since = timezone.now() - timedelta(hours=24)
    qs = NotificationDelivery.objects.filter(created_at__gte=since)
    total = qs.count()
    sent = qs.filter(status=NotificationDelivery.Status.SENT).count()
    return {
        "total": total,
        "delivered": sent,
        "failed": qs.filter(status=NotificationDelivery.Status.FAILED).count(),
        "pending": qs.filter(status=NotificationDelivery.Status.PENDING).count(),
        "delivery_rate": round((sent / total) * 100, 1) if total else 0,
    }
