"""Node-facing helpers for persisting agent client addresses."""

from __future__ import annotations

from common.http.client_ip import client_ip_from_meta, client_ip_from_scope

__all__ = ["resolve_agent_client_ip", "resolve_agent_client_ip_from_scope"]


def resolve_agent_client_ip(request) -> str | None:
    return client_ip_from_meta(getattr(request, "META", None))


def resolve_agent_client_ip_from_scope(scope: dict | None) -> str | None:
    return client_ip_from_scope(scope)
