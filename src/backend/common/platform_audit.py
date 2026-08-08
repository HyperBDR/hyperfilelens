"""Platform staff audit log write hook (OSS SPI; EE/platform_ops registers writer)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest

_Writer = Callable[..., Any]
_writer: _Writer | None = None


def register_platform_audit_writer(writer: _Writer | None) -> None:
    """Register the active platform audit writer (None = no-op)."""
    global _writer
    _writer = writer


def write_platform_audit_log(
    *,
    request: HttpRequest | None = None,
    action: str,
    target_type: str,
    target_id: str = "",
    org_key: str = "",
    details: dict | None = None,
    result: str = "success",
    actor_id: int | None = None,
    **kwargs: Any,
) -> Any:
    """Write a platform audit entry if a writer is registered; otherwise no-op."""
    if _writer is None:
        return None
    return _writer(
        request=request,
        action=action,
        target_type=target_type,
        target_id=target_id,
        org_key=org_key,
        details=details,
        result=result,
        actor_id=actor_id,
        **kwargs,
    )
