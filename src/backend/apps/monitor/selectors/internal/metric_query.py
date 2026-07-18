"""Read system metric time series."""

from __future__ import annotations

from datetime import datetime

from apps.monitor.models import SystemMetric

MAX_SERIES_POINTS = 2000


def list_metrics_between(*, since: datetime, until: datetime, host_id=None) -> list[SystemMetric]:
    qs = SystemMetric.objects.filter(timestamp__gte=since, timestamp__lte=until)
    if host_id is not None:
        qs = qs.filter(host_id=host_id)
    return list(qs.order_by("timestamp")[:MAX_SERIES_POINTS])
