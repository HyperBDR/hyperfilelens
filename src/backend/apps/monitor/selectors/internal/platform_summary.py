"""Cross-domain aggregates for platform monitor (read-only)."""

from __future__ import annotations

from datetime import datetime

from apps.alert.selectors.interface import platform_alert_counts, recent_active_alerts
from apps.iam.models import Organization
from apps.notification.selectors.interface import failed_delivery_count
from apps.task.selectors.interface import platform_task_counts, recent_failed_tasks


def active_organization_count() -> int:
    return Organization.objects.filter(is_active=True).count()


def offline_node_count() -> int:
    try:
        from apps.node.models import Node

        return Node.objects.filter(status=Node.Status.OFFLINE).count()
    except Exception:
        return 0


def platform_monitor_payload(*, since: datetime) -> dict:
    alert_counts = platform_alert_counts()
    task_counts = platform_task_counts(since=since)
    return {
        "organizations_active": active_organization_count(),
        "alerts_firing": alert_counts["firing"],
        "alerts_acknowledged": alert_counts["acknowledged"],
        "tasks_running": task_counts["running"],
        "tasks_failed_24h": task_counts["failed_24h"],
        "tasks_failed_total": task_counts["failed_total"],
        "notifications_failed_total": failed_delivery_count(),
        "nodes_offline": offline_node_count(),
        "recent_alerts": recent_active_alerts(limit=10),
        "recent_failed_tasks": recent_failed_tasks(limit=10),
    }
