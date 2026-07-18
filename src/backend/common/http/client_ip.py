"""Resolve the original client IP behind reverse proxies."""

from __future__ import annotations


def client_ip_from_meta(meta: dict | None) -> str | None:
    """Return the left-most client IP from request META or ASGI-derived headers."""
    if not meta:
        return None
    forwarded = str(meta.get("HTTP_X_FORWARDED_FOR", "") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    remote = meta.get("REMOTE_ADDR")
    return str(remote).strip() if remote else None


def client_ip_from_scope(scope: dict | None) -> str | None:
    """Return client IP from a Channels/WebSocket ASGI scope."""
    if not scope:
        return None
    headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
    forwarded = headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and client:
        host = str(client[0]).strip()
        return host or None
    return None
