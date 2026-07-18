"""Collect host metrics from the control-plane process (psutil with fallback)."""

from __future__ import annotations

import os
import shutil

from django.conf import settings


def collect_system_sample() -> dict:
    try:
        import psutil
    except ImportError:
        return _collect_fallback()

    cpu_freq = psutil.cpu_freq()
    virtual_memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disks = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, FileNotFoundError, OSError):
            continue
        disks.append(
            {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        )

    disk_io = []
    counters = psutil.disk_io_counters(perdisk=True) or {}
    for name, item in counters.items():
        disk_io.append(
            {
                "name": name,
                "read_bytes": item.read_bytes,
                "write_bytes": item.write_bytes,
                "read_count": item.read_count,
                "write_count": item.write_count,
                "read_time": item.read_time,
                "write_time": item.write_time,
            }
        )

    networks = []
    addresses = psutil.net_if_addrs()
    for name, item in (psutil.net_io_counters(pernic=True) or {}).items():
        networks.append(
            {
                "name": name,
                "bytes_sent": item.bytes_sent,
                "bytes_recv": item.bytes_recv,
                "packets_sent": item.packets_sent,
                "packets_recv": item.packets_recv,
                "errin": item.errin,
                "errout": item.errout,
                "dropin": item.dropin,
                "dropout": item.dropout,
                "addresses": [addr.address for addr in addresses.get(name, [])],
            }
        )

    load_average = list(os.getloadavg()) if hasattr(os, "getloadavg") else []
    return {
        "cpu": {
            "usage_percent": psutil.cpu_percent(interval=0.1),
            "per_cpu_percent": psutil.cpu_percent(interval=None, percpu=True),
            "logical_cores": psutil.cpu_count(),
            "physical_cores": psutil.cpu_count(logical=False),
            "frequency_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
        },
        "memory": {
            "total": virtual_memory.total,
            "used": virtual_memory.used,
            "available": virtual_memory.available,
            "percent": virtual_memory.percent,
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "free": swap.free,
            "percent": swap.percent,
        },
        "disks": disks,
        "disk_io": disk_io,
        "networks": networks,
        "load_average": load_average,
        "metadata": {"collector": "psutil"},
    }


def _collect_fallback() -> dict:
    usage = shutil.disk_usage(settings.BASE_DIR)
    load_average = list(os.getloadavg()) if hasattr(os, "getloadavg") else []
    return {
        "cpu": {
            "usage_percent": 0,
            "per_cpu_percent": [],
            "logical_cores": os.cpu_count(),
            "physical_cores": None,
            "frequency_mhz": None,
        },
        "memory": {"total": 0, "used": 0, "available": 0, "percent": 0},
        "swap": {"total": 0, "used": 0, "free": 0, "percent": 0},
        "disks": [
            {
                "device": "default",
                "mountpoint": str(settings.BASE_DIR),
                "fstype": "",
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round((usage.used / usage.total) * 100, 2) if usage.total else 0,
            }
        ],
        "disk_io": [],
        "networks": [],
        "load_average": load_average,
        "metadata": {"collector": "fallback"},
    }
