"""Channels group names for Agent WebSocket sessions."""

from __future__ import annotations

import re


def agent_group_name(*, node_id: int) -> str:
    """
    Redis Channel Layer group for one Agent node.

    Must use only alphanumerics, hyphens, underscores, or periods (no ``:``).
    """
    return f"agent.{int(node_id)}"


def ws_instance_group_name(*, ws_instance_id: str) -> str:
    """Deployment-drain group scoped to one Daphne process instance."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", str(ws_instance_id).strip())
    return f"ws-instance.{safe or 'unknown'}"[:100]
