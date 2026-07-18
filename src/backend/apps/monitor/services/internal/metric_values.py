"""Extract scalar metric values from system/resource JSON samples."""

from __future__ import annotations

from apps.monitor.models import SystemMetric


def value_from_system_metric(metric: SystemMetric, metric_key: str) -> float | None:
    cpu = metric.cpu or {}
    memory = metric.memory or {}
    swap = metric.swap or {}
    disks = metric.disk_io if isinstance(metric.disk_io, list) else []
    disk_list = metric.disks if isinstance(metric.disks, list) else []
    load = metric.load_average if isinstance(metric.load_average, list) else []
    networks = metric.networks if isinstance(metric.networks, list) else []

    mapping = {
        "cpu_usage": cpu.get("usage_percent"),
        "memory_usage": memory.get("percent"),
        "swap_usage": swap.get("percent"),
    }
    if metric_key in mapping:
        raw = mapping[metric_key]
        return float(raw) if raw is not None else None
    if metric_key == "disk_usage":
        percents = [d.get("percent") for d in disk_list if d.get("percent") is not None]
        return float(max(percents)) if percents else None
    if metric_key == "disk_read_bytes":
        total = sum(int(d.get("read_bytes") or 0) for d in disks)
        return float(total)
    if metric_key == "disk_write_bytes":
        total = sum(int(d.get("write_bytes") or 0) for d in disks)
        return float(total)
    if metric_key == "network_rx":
        total = sum(int(n.get("bytes_recv") or 0) for n in networks)
        return float(total)
    if metric_key == "network_tx":
        total = sum(int(n.get("bytes_sent") or 0) for n in networks)
        return float(total)
    if metric_key == "load_1m" and len(load) > 0:
        return float(load[0])
    if metric_key == "load_5m" and len(load) > 1:
        return float(load[1])
    if metric_key == "load_15m" and len(load) > 2:
        return float(load[2])
    return None


def value_from_resource_metrics(metrics: dict, metric_key: str) -> float | None:
    if not isinstance(metrics, dict):
        return None
    raw = metrics.get(metric_key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
