"""Public write/read orchestration for control-plane monitoring."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from django.utils import timezone

from apps.monitor.models import DeploymentHost, SystemMetric
from apps.monitor.selectors.interface import list_system_metrics
from apps.monitor.services.internal.collector import collect_system_sample
from apps.monitor.services.internal.deployment_host import (
    host_to_monitor_dict,
    touch_local_deployment_host,
)
from apps.monitor.services.internal.time_range import resolve_time_range

__all__ = [
    "build_system_monitor_payload",
    "collect_and_persist_sample",
    "cleanup_old_metrics",
    "list_deployment_hosts",
    "metric_to_dict",
    "resolve_monitor_time_range",
]


def resolve_monitor_time_range(
    *,
    hours_raw: str | None = None,
    start_at_raw: str | None = None,
    end_at_raw: str | None = None,
):
    return resolve_time_range(
        hours_raw=hours_raw,
        start_at_raw=start_at_raw,
        end_at_raw=end_at_raw,
    )


def collect_and_persist_sample(*, host: DeploymentHost | None = None) -> SystemMetric:
    """Write path: register host and persist one sample (Celery worker only in production)."""
    if host is None:
        host = touch_local_deployment_host()
    sample = collect_system_sample()
    return SystemMetric.objects.create(host=host, **sample)


def metric_to_dict(metric: SystemMetric) -> dict:
    return {
        "timestamp": metric.timestamp.isoformat(),
        "cpu": metric.cpu,
        "memory": metric.memory,
        "swap": metric.swap,
        "disks": metric.disks,
        "disk_io": metric.disk_io,
        "networks": metric.networks,
        "load_average": metric.load_average,
        "metadata": metric.metadata,
    }


def _resolve_target_host(host_id: str | None) -> DeploymentHost | None:
    if host_id:
        try:
            parsed = uuid.UUID(str(host_id))
        except ValueError:
            return None
        return DeploymentHost.objects.filter(id=parsed).first()
    return DeploymentHost.objects.order_by("-last_seen_at", "hostname").first()


def list_deployment_hosts() -> list[dict]:
    from apps.monitor.services.internal.deployment_host import host_to_dict, list_unique_deployment_hosts

    return [host_to_dict(host) for host in list_unique_deployment_hosts()]


def build_system_monitor_payload(*, since: datetime, until: datetime, host_id: str | None = None) -> dict | None:
    """Read path: return stored metrics only (no live psutil sampling)."""
    target_host = _resolve_target_host(host_id)
    if target_host is None:
        return None

    metrics = list_system_metrics(since=since, until=until, host_id=target_host.id)
    series = [metric_to_dict(m) for m in metrics]
    current = series[-1] if series else {}

    host_payload = host_to_monitor_dict(target_host)
    host_payload["boot_time"] = target_host.boot_time

    return {
        "host": host_payload,
        "host_id": str(target_host.id),
        "range": {
            "start_at": since.isoformat(),
            "end_at": until.isoformat(),
            "count": len(series),
        },
        "current": current,
        "series": series,
    }


def cleanup_old_metrics(*, days_to_keep: int = 7) -> int:
    cutoff = timezone.now() - timedelta(days=days_to_keep)
    count, _ = SystemMetric.objects.filter(timestamp__lt=cutoff).delete()
    return count
