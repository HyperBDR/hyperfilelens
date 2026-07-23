"""Read-only aggregates for the Admin Console overview."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.alert.models import AlertRecord
from apps.lens_bridge.models import LensUsageLedger
from apps.lens_bridge.services import sl_client
from apps.monitor.selectors.internal.platform_summary import platform_monitor_payload
from apps.node.models import Node
from apps.node.services.internal.agent_release import (
    latest_published_agent_version,
    semver_compare,
)
from apps.notification.constants import NotificationLogStatus
from apps.notification.models import NotificationLog
from apps.platform_ops.api.serializers.platform import (
    PlatformAlertRowSerializer,
    PlatformTaskRowSerializer,
)
from apps.platform_ops.selectors.internal.health import list_platform_alerts
from apps.platform_ops.selectors.internal.org_lookup import organization_map
from apps.platform_ops.selectors.internal.system import system_health_payload
from apps.storage.repositories.models import Repository
from apps.subscription.models import License, OrganizationSubscription
from apps.task.models import Task
from apps.task.selectors.interface import recent_failed_tasks


SUPPORTED_RANGE_HOURS = (1, 24, 168, 720)
REPOSITORY_WARNING_PERCENT = 80.0
EXPIRY_WARNING_DAYS = 30


def normalize_range_hours(raw: Any) -> int:
    """Return a supported overview range, defaulting to 24 hours."""

    try:
        hours = int(raw)
    except (TypeError, ValueError):
        return 24
    return hours if hours in SUPPORTED_RANGE_HOURS else 24


def _repository_summary() -> dict[str, int | float | None]:
    rows = Repository.objects.exclude(status=Repository.Status.REMOVED).values(
        "status",
        "health",
        "capacity_bytes",
        "estimated_usage_bytes",
        "physical_usage_bytes",
    )
    at_risk = 0
    capacity_warning = 0
    max_usage_percent: float | None = None
    failed_statuses = {
        Repository.Status.CREATE_FAILED,
        Repository.Status.REMOVE_FAILED,
    }
    for row in rows:
        capacity = int(row["capacity_bytes"] or 0)
        physical = row["physical_usage_bytes"]
        used = int(physical if physical is not None else row["estimated_usage_bytes"] or 0)
        usage_percent = (used / capacity) * 100 if capacity > 0 else None
        if usage_percent is not None:
            max_usage_percent = max(max_usage_percent or 0.0, usage_percent)
        capacity_at_risk = bool(
            usage_percent is not None and usage_percent >= REPOSITORY_WARNING_PERCENT
        )
        if capacity_at_risk:
            capacity_warning += 1
        if (
            row["health"] != Repository.Health.ONLINE
            or row["status"] in failed_statuses
            or capacity_at_risk
        ):
            at_risk += 1
    return {
        "repositories_at_risk": at_risk,
        "repositories_capacity_warning": capacity_warning,
        "repository_max_usage_percent": (
            round(max_usage_percent, 1) if max_usage_percent is not None else None
        ),
    }


def _ai_summary(*, since: datetime) -> dict[str, int | float | None]:
    rows = LensUsageLedger.objects.filter(occurred_at__gte=since)
    total = rows.count()
    successful = rows.filter(
        run_status__in=["done", "success", "completed"],
    ).count()
    failed = rows.filter(run_status__in=["failed", "error"]).count()
    terminal = successful + failed
    return {
        "ai_runs_total": total,
        "ai_runs_failed": failed,
        "ai_success_rate": round((successful / terminal) * 100, 1) if terminal else None,
    }


def _outdated_agent_count() -> tuple[int, str]:
    latest = latest_published_agent_version()
    if latest == "0.0.0":
        return 0, latest
    count = sum(
        1
        for version in Node.objects.exclude(version="").values_list("version", flat=True)
        if semver_compare(str(version), latest) < 0
    )
    return count, latest


def _expiring_account_count(*, now: datetime) -> int:
    warning_at = now + timedelta(days=EXPIRY_WARNING_DAYS)
    license_orgs = License.objects.filter(
        status=License.Status.ACTIVE,
        expires_at__gte=now,
        expires_at__lte=warning_at,
    ).values_list("organization_id", flat=True)
    subscription_orgs = OrganizationSubscription.objects.filter(
        status="active",
        ends_at__gte=now,
        ends_at__lte=warning_at,
    ).values_list("organization_id", flat=True)
    return len(set(license_orgs).union(subscription_orgs))


def _service_status(raw: str) -> str:
    value = str(raw or "unknown").lower()
    if value == "ok":
        return "healthy"
    if value in {"error", "offline", "unreachable"}:
        return "unavailable"
    return "degraded"


def _service_detail(key: str, payload: dict[str, Any]) -> str:
    if payload.get("error"):
        return "Health check failed"
    if key in {"database", "redis"} and payload.get("latency_ms") is not None:
        return f'{payload["latency_ms"]} ms'
    if key == "workers":
        workers = int(payload.get("worker_count") or 0)
        active = int(payload.get("active_tasks") or 0)
        return f"{workers} workers · {active} active"
    if key == "sourcelens":
        if not payload.get("configured"):
            return "Not configured"
        if not payload.get("reachable"):
            return "Unreachable"
        return "Authenticated" if payload.get("authenticated") else "Authentication failed"
    return ""


def _system_health_summary() -> dict[str, Any]:
    health = system_health_payload()
    lens = sl_client.ping(timeout=2)
    lens_status = (
        "ok"
        if lens.get("reachable") and lens.get("authenticated")
        else "unknown"
        if not lens.get("configured")
        else "error"
        if not lens.get("reachable")
        else "degraded"
    )
    raw_services = [
        ("api", "API", health.get("api") or {}),
        ("database", "Database", health.get("database") or {}),
        ("redis", "Redis", health.get("redis") or {}),
        ("workers", "Workers", health.get("celery") or {}),
        ("sourcelens", "SourceLens", {**lens, "status": lens_status}),
    ]
    services = [
        {
            "key": key,
            "label": label,
            "status": _service_status(str(payload.get("status") or "unknown")),
            "detail": _service_detail(key, payload),
        }
        for key, label, payload in raw_services
    ]
    healthy = sum(row["status"] == "healthy" for row in services)
    degraded = sum(row["status"] == "degraded" for row in services)
    unavailable = sum(row["status"] == "unavailable" for row in services)
    overall = "unavailable" if unavailable else "degraded" if degraded else "healthy"
    return {
        "overall_status": overall,
        "healthy_count": healthy,
        "degraded_count": degraded,
        "unavailable_count": unavailable,
        "services": services,
        "checked_at": health.get("checked_at") or timezone.now().isoformat(),
    }


def _bucket_counts(
    timestamps: Iterable[datetime],
    *,
    since: datetime,
    until: datetime,
    bucket_count: int,
) -> list[int]:
    counts = [0] * bucket_count
    span = max((until - since).total_seconds(), 1)
    for value in timestamps:
        position = (value - since).total_seconds() / span
        index = min(max(int(position * bucket_count), 0), bucket_count - 1)
        counts[index] += 1
    return counts


def _activity_series(*, since: datetime, until: datetime, hours: int) -> list[dict[str, Any]]:
    bucket_count = 12 if hours <= 24 else 14 if hours <= 168 else 15
    alert_times = AlertRecord.objects.annotate(
        activity_at=Coalesce("last_triggered_at", "created_at"),
    ).filter(activity_at__gte=since, activity_at__lte=until).values_list(
        "activity_at",
        flat=True,
    )
    task_times = Task.objects.filter(
        status__in=[Task.Status.FAILED, Task.Status.TIMEOUT],
    ).annotate(
        activity_at=Coalesce("finished_at", "updated_at"),
    ).filter(activity_at__gte=since, activity_at__lte=until).values_list(
        "activity_at",
        flat=True,
    )
    alert_counts = _bucket_counts(
        alert_times,
        since=since,
        until=until,
        bucket_count=bucket_count,
    )
    task_counts = _bucket_counts(
        task_times,
        since=since,
        until=until,
        bucket_count=bucket_count,
    )
    step = (until - since) / bucket_count
    return [
        {
            "started_at": (since + step * index).isoformat(),
            "alerts": alert_counts[index],
            "failed_tasks": task_counts[index],
        }
        for index in range(bucket_count)
    ]


def _failed_task_count(*, since: datetime, until: datetime) -> int:
    """Count failed and timed-out tasks whose terminal update is in range."""
    return (
        Task.objects.filter(
            status__in=[Task.Status.FAILED, Task.Status.TIMEOUT],
        )
        .annotate(activity_at=Coalesce("finished_at", "updated_at"))
        .filter(activity_at__gte=since, activity_at__lte=until)
        .count()
    )


def platform_overview_payload(*, hours: int) -> dict[str, Any]:
    """Build the complete read-only Admin Console overview response."""

    now = timezone.now()
    since = now - timedelta(hours=hours)
    summary = platform_monitor_payload(since=since)
    repository = _repository_summary()
    ai = _ai_summary(since=since)
    outdated_agents, latest_agent_version = _outdated_agent_count()
    notification_failures = NotificationLog.objects.filter(
        status=NotificationLogStatus.FAILED,
        sent_at__gte=since,
    ).count()
    expiring_accounts = _expiring_account_count(now=now)
    alerts = list(list_platform_alerts()[:8])
    failed_tasks = list(recent_failed_tasks(limit=8))
    org_map = organization_map(task.organization_id for task in failed_tasks)
    metrics = {
        "organizations_active": summary["organizations_active"],
        "alerts_firing": summary["alerts_firing"],
        "alerts_acknowledged": summary["alerts_acknowledged"],
        "tasks_running": summary["tasks_running"],
        "tasks_failed_in_range": _failed_task_count(since=since, until=now),
        "tasks_failed_24h": summary["tasks_failed_24h"],
        "tasks_failed_total": summary["tasks_failed_total"],
        "notifications_failed_in_range": notification_failures,
        "notifications_failed_total": summary["notifications_failed_total"],
        "nodes_offline": summary["nodes_offline"],
        "outdated_agents": outdated_agents,
        "latest_agent_version": latest_agent_version,
        "expiring_accounts": expiring_accounts,
        **repository,
        **ai,
    }
    return {
        "range_hours": hours,
        "generated_at": now.isoformat(),
        "metrics": metrics,
        "system_health": _system_health_summary(),
        "activity_series": _activity_series(since=since, until=now, hours=hours),
        "recent_alerts": PlatformAlertRowSerializer(alerts, many=True).data,
        "recent_failed_tasks": PlatformTaskRowSerializer(
            failed_tasks,
            many=True,
            context={"org_map": org_map},
        ).data,
    }
