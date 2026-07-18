"""
Record login metadata for account security audit display.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import urllib.error
import urllib.request

from django.contrib.auth.models import User
from django.utils import timezone

from apps.audit.constants import AuditAction, AuditResourceType
from apps.audit.services.interface import _client_ip, write_audit_log
from apps.iam.models import Organization
from apps.iam.profile_models import Profile

logger = logging.getLogger(__name__)

LOGIN_LOCATION_LOCAL_NETWORK = "local_network"
_LEGACY_LOCAL_NETWORK_LABEL = "\u5c40\u57df\u7f51"
_LEGACY_LOCAL_NETWORK_LABELS = frozenset(
    {LOGIN_LOCATION_LOCAL_NETWORK, _LEGACY_LOCAL_NETWORK_LABEL},
)


def normalize_login_location(location: str | None) -> str | None:
    """Return a locale-neutral location code for API consumers."""
    if not location:
        return None
    if location in _LEGACY_LOCAL_NETWORK_LABELS:
        return LOGIN_LOCATION_LOCAL_NETWORK
    return location


def resolve_login_organization(user: User, org_key: str | None = None) -> Organization | None:
    from apps.iam.models import Membership

    if org_key:
        membership = (
            Membership.objects.filter(
                user=user,
                organization__key=org_key,
                is_active=True,
                organization__is_active=True,
            )
            .select_related("organization")
            .first()
        )
        if membership:
            return membership.organization

    membership = (
        Membership.objects.filter(user=user, is_active=True, organization__is_active=True)
        .select_related("organization")
        .first()
    )
    return membership.organization if membership else None


def resolve_login_location(ip: str | None, request) -> str:
    """Best-effort location label for a login IP."""
    for header in ("HTTP_CF_IPCITY", "HTTP_X_CITY", "HTTP_X_APPENGINE_CITY"):
        value = (request.META.get(header) or "").strip()
        if value:
            return value

    country = (request.META.get("HTTP_CF_IPCOUNTRY") or "").strip()
    if country and country not in {"XX", "T1"}:
        return country

    if not ip:
        return ""

    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return LOGIN_LOCATION_LOCAL_NETWORK
    except ValueError:
        return ""

    try:
        req = urllib.request.Request(
            f"http://ip-api.com/json/{ip}?fields=status,city,country",
            headers={"User-Agent": "HyperFileLens/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == "success":
            city = (data.get("city") or "").strip()
            if city:
                return city
            return (data.get("country") or "").strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        logger.debug("IP geolocation lookup failed for %s", ip, exc_info=True)

    return ""


def serialize_security_audit(audit: dict) -> dict:
    last_at = audit.get("last_login_at")
    return {
        "last_login_at": last_at.isoformat() if last_at else None,
        "last_login_ip": audit.get("last_login_ip") or None,
        "last_login_location": normalize_login_location(audit.get("last_login_location")),
    }


def _get_security_audit_from_profile(user: User) -> dict:
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = None

    last_ip = None
    last_location = None
    last_at = user.last_login

    if profile is not None:
        last_ip = profile.last_login_ip or profile.previous_login_ip or None
        last_location = profile.last_login_location or profile.previous_login_location or None
        if not last_at:
            last_at = profile.previous_login_at

    return {
        "last_login_at": last_at,
        "last_login_ip": last_ip or None,
        "last_login_location": last_location or None,
    }


def _get_security_audit_from_audit_log(user: User) -> dict | None:
    from apps.audit.constants import AuditAction, AuditResult
    from apps.audit.models import AuditLog

    log = (
        AuditLog.objects.filter(
            user=user,
            action=AuditAction.LOGIN,
            result=AuditResult.SUCCESS,
        )
        .order_by("-created_at")
        .first()
    )
    if log is None:
        return None

    metadata = log.metadata or {}
    return {
        "last_login_at": log.created_at,
        "last_login_ip": str(log.ip_address) if log.ip_address else None,
        "last_login_location": metadata.get("location") or None,
    }


def get_security_audit(user: User) -> dict:
    profile_data = _get_security_audit_from_profile(user)
    if profile_data.get("last_login_at"):
        return profile_data

    audit_log_data = _get_security_audit_from_audit_log(user)
    if audit_log_data:
        return audit_log_data

    return profile_data


def record_user_login(
    user: User,
    request,
    *,
    organization: Organization | None = None,
) -> None:
    """Persist previous-login audit fields and write a login audit log entry."""
    ip = _client_ip(request) or ""
    location = resolve_login_location(ip, request)
    now = timezone.now()

    profile, _ = Profile.objects.get_or_create(user=user)

    try:
        profile.previous_login_at = user.last_login
        profile.previous_login_ip = profile.last_login_ip
        profile.previous_login_location = profile.last_login_location
        profile.last_login_ip = ip
        profile.last_login_location = location
        profile.save(
            update_fields=[
                "previous_login_at",
                "previous_login_ip",
                "previous_login_location",
                "last_login_ip",
                "last_login_location",
            ]
        )

        user.last_login = now
        user.save(update_fields=["last_login"])
    except Exception:
        logger.exception("Failed to persist login audit profile fields for user %s", user.id)

    organization = organization or resolve_login_organization(user)
    if organization is None:
        return

    try:
        write_audit_log(
            organization=organization,
            user=user,
            action=AuditAction.LOGIN,
            resource_type=AuditResourceType.USER,
            resource_id=str(user.id),
            resource_name=user.email or user.username,
            ip_address=ip or None,
            user_agent=str(request.META.get("HTTP_USER_AGENT", "") or "")[:500],
            metadata={"location": location},
            request_method=getattr(request, "method", ""),
            request_path=getattr(request, "path", ""),
        )
    except Exception:
        logger.warning("Failed to write login audit log for user %s", user.id, exc_info=True)
