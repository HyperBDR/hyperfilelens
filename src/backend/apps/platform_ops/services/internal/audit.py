"""Write platform audit log entries."""

from __future__ import annotations

from django.http import HttpRequest

from apps.platform_ops.models import PlatformAuditLog


def _client_ip(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.META.get("REMOTE_ADDR")


def write_platform_audit_log(
    *,
    request: HttpRequest | None,
    action: str,
    target_type: str,
    target_id: str = "",
    org_key: str = "",
    details: dict | None = None,
    result: str = PlatformAuditLog.Result.SUCCESS,
) -> PlatformAuditLog:
    actor = request.user if request and request.user.is_authenticated else None
    user_agent = ""
    if request:
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    return PlatformAuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        org_key=(org_key or "").strip(),
        details=details or {},
        ip_address=_client_ip(request),
        user_agent=user_agent,
        result=result,
    )
