"""Build node host-monitor dashboard payloads from ResourceMetric samples."""

from __future__ import annotations

from datetime import datetime

from apps.alert.constants import ResourceType
from apps.monitor.models import ResourceMetric
from apps.node.models import Node
from apps.node.models.base import NodeRole

_ROLE_TO_RESOURCE_TYPE = {
    NodeRole.AGENT: ResourceType.AGENT_PROXY,
    NodeRole.PROXY: ResourceType.SYNC_PROXY,
    NodeRole.GATEWAY: ResourceType.GATEWAY,
}


def resource_type_for_role(role: str) -> str | None:
    try:
        return _ROLE_TO_RESOURCE_TYPE.get(NodeRole(role))
    except ValueError:
        return None


def _sample_from_metrics(row: ResourceMetric) -> dict:
    metrics = row.metrics if isinstance(row.metrics, dict) else {}
    sample = {
        "timestamp": row.timestamp.isoformat(),
        "cpu": metrics.get("cpu") or {},
        "memory": metrics.get("memory") or {},
        "swap": metrics.get("swap") or {},
        "disks": metrics.get("disks") or [],
        "disk_io": metrics.get("disk_io") or metrics.get("diskIo") or [],
        "networks": metrics.get("networks") or [],
        "load_average": metrics.get("load_average") or metrics.get("loadAverage") or [],
        "metadata": metrics.get("metadata") or {},
    }
    if metrics.get("boot_time") is not None:
        sample["boot_time"] = metrics["boot_time"]
    return sample


def _host_from_node(node: Node, current: dict | None = None) -> dict:
    meta = node.metadata if isinstance(node.metadata, dict) else {}
    inventory = meta.get("inventory") if isinstance(meta.get("inventory"), dict) else {}
    hostname = (
        str(inventory.get("hostname") or "")
        or str(node.name or "")
        or str(node.id)
    )
    platform_parts = [
        str(inventory.get("os") or "").strip(),
        str(inventory.get("arch") or "").strip(),
    ]
    platform = " ".join(p for p in platform_parts if p)
    boot_time = None
    if current and current.get("boot_time") is not None:
        boot_time = current.get("boot_time")
    elif meta.get("boot_time") is not None:
        boot_time = meta.get("boot_time")
    host = {
        "hostname": hostname,
        "platform": platform,
        "role": node.role,
        "node_id": node.id,
        "node_name": node.name,
    }
    if boot_time is not None:
        host["boot_time"] = boot_time
    return host


def build_node_monitor_payload(*, node: Node, since: datetime, until: datetime) -> dict:
    resource_type = resource_type_for_role(node.role)
    if not resource_type:
        return {
            "host": _host_from_node(node),
            "range": {"start_at": since.isoformat(), "end_at": until.isoformat(), "count": 0},
            "current": {},
            "series": [],
        }

    rows = list(
        ResourceMetric.objects.filter(
            organization_id=node.organization_id,
            resource_type=resource_type,
            resource_id=str(node.id),
            timestamp__gte=since,
            timestamp__lte=until,
        ).order_by("timestamp")[:2000]
    )
    series = [_sample_from_metrics(row) for row in rows]
    current = series[-1] if series else {}
    return {
        "host": _host_from_node(node, current),
        "range": {
            "start_at": since.isoformat(),
            "end_at": until.isoformat(),
            "count": len(series),
        },
        "current": current,
        "series": series,
        "resource_type": resource_type,
        "resource_id": str(node.id),
    }


def list_monitor_nodes(*, organization_id: int, role: str | None = None) -> list[Node]:
    qs = Node.objects.filter(organization_id=organization_id).order_by("name", "id")
    if role:
        qs = qs.filter(role=role)
    return list(qs)
