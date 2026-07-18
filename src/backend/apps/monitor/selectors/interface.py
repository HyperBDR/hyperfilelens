"""Public read API for monitor app."""

from __future__ import annotations

from datetime import datetime

from apps.monitor.models import SystemMetric
from apps.monitor.selectors.internal.metric_query import list_metrics_between

__all__ = ["list_system_metrics"]


def list_system_metrics(*, since: datetime, until: datetime, host_id=None) -> list[SystemMetric]:
    return list_metrics_between(since=since, until=until, host_id=host_id)
