"""Resolve default display names for enrolled Agent / Proxy nodes."""

from __future__ import annotations

from typing import Any

from apps.node.models import Node

_AUTO_NODE_NAMES = frozenset({"", "new-node", "node", "new node"})


def hostname_from_metadata(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    inv = metadata.get("inventory")
    sources: list[dict[str, Any]] = []
    if isinstance(inv, dict):
        sources.append(inv)
    sources.append(metadata)
    for source in sources:
        hostname = str(source.get("hostname") or "").strip()
        if hostname:
            return hostname
    return ""


def is_auto_assigned_node_name(name: str | None) -> bool:
    return str(name or "").strip().lower() in _AUTO_NODE_NAMES


def resolve_registration_node_name(*, payload: dict[str, Any], fallback: str = "new-node") -> str:
    """Prefer hostname from registration metadata over placeholder names."""
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    hostname = hostname_from_metadata(meta)
    explicit = str(payload.get("name") or "").strip()
    if hostname:
        return hostname
    if explicit and not is_auto_assigned_node_name(explicit):
        return explicit
    return explicit or fallback


def resolve_inventory_node_name(*, node: Node, inventory: dict[str, Any]) -> str | None:
    """Return hostname when the node still carries an auto-assigned name."""
    if not is_auto_assigned_node_name(node.name):
        return None
    hostname = str(inventory.get("hostname") or "").strip()
    if not hostname:
        return None
    return hostname


def uniquify_node_name(
    *,
    organization_id: int,
    name: str,
    exclude_node_id: int | None = None,
) -> str:
    qs = Node.objects.filter(
        organization_id=organization_id,
        name=name,
        is_deleted=False,
    )
    if exclude_node_id is not None:
        qs = qs.exclude(pk=exclude_node_id)
    if not qs.exists():
        return name
    if exclude_node_id is not None:
        return f"{name}-{exclude_node_id}"
    return name
