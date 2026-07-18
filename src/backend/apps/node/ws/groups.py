"""Channels group names for Agent WebSocket sessions."""

from __future__ import annotations


def agent_group_name(*, node_id: int) -> str:
    """
    Redis Channel Layer group for one Agent node.

    Must use only alphanumerics, hyphens, underscores, or periods (no ``:``).
    """
    return f"agent.{int(node_id)}"
