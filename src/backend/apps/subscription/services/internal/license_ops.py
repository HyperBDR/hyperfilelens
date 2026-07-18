"""License activation and lookup."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from django.conf import settings
from django.db import transaction

from apps.iam.models import Organization
from apps.subscription.constants import DEFAULT_LIMITS, UNLIMITED
from apps.subscription.models import License, MachineCode
from apps.subscription.services.internal.crypto import verify_activation_code
from apps.subscription.services.internal.machine_code import generate_machine_code
from apps.subscription.services.internal.usage import collect_usage_stats


def _map_limits(raw: dict) -> dict:
    """Map xxz limit keys to organization license fields."""
    return {
        "max_organizations": raw.get(
            "max_organizations", raw.get("max_tenants", DEFAULT_LIMITS["max_organizations"])
        ),
        "max_users": raw.get("max_users", DEFAULT_LIMITS["max_users"]),
        "max_nodes": raw.get("max_nodes", raw.get("max_proxies", DEFAULT_LIMITS["max_nodes"])),
        "max_storage_gb": raw.get("max_storage_gb", DEFAULT_LIMITS["max_storage_gb"]),
        "max_gateways": raw.get("max_gateways", DEFAULT_LIMITS["max_gateways"]),
        "ai_insights_quota": raw.get("ai_insights_quota", DEFAULT_LIMITS["ai_insights_quota"]),
        "max_tasks": raw.get(
            "max_tasks",
            raw.get("max_backup_tasks", DEFAULT_LIMITS["max_tasks"]),
        ),
        "max_alert_policies": raw.get(
            "max_alert_policies",
            raw.get("max_policies", DEFAULT_LIMITS["max_alert_policies"]),
        ),
    }


def _dev_unlimited_limits() -> dict:
    return {k: UNLIMITED for k in DEFAULT_LIMITS}


def get_or_create_machine_code(*, organization: Organization, user, force: bool = False) -> str:
    existing = MachineCode.objects.filter(organization=organization).first()
    if existing and not force:
        return existing.code
    code, components = generate_machine_code(
        organization_id=organization.id,
        user_id=user.id if user and user.is_authenticated else 0,
    )
    if existing:
        existing.code = code
        existing.hostname = components.get("hostname", "")
        existing.source = components.get("source", "")
        existing.user = user if user and user.is_authenticated else None
        existing.save(update_fields=["code", "hostname", "source", "user"])
        return code
    MachineCode.objects.create(
        code=code,
        organization=organization,
        user=user if user and user.is_authenticated else None,
        hostname=components.get("hostname", ""),
        source=components.get("source", ""),
    )
    return code


def get_active_license(*, organization: Organization) -> License | None:
    try:
        lic = organization.license
    except License.DoesNotExist:
        return None
    if lic.is_valid:
        return lic
    if lic.expires_at and lic.expires_at < timezone.now() and lic.status == License.Status.ACTIVE:
        lic.status = License.Status.EXPIRED
        lic.save(update_fields=["status", "updated_at"])
    return lic if lic.is_valid else None


def build_current_payload(*, organization: Organization, user) -> dict:
    machine_code = get_or_create_machine_code(organization=organization, user=user)
    license_obj = get_active_license(organization=organization)
    usage = collect_usage_stats(organization_id=organization.id)
    if not license_obj:
        return {
            "is_valid": False,
            "message": "No active license",
            "machine_code": machine_code,
            "usage": usage,
            "limits": dict(DEFAULT_LIMITS),
            "organization_name": organization.name,
            "enforcement_enabled": False,
        }
    return {
        "is_valid": license_obj.is_valid,
        "license": license_obj,
        "limits": license_obj.get_limits(),
        "days_until_expiry": license_obj.days_until_expiry,
        "usage": usage,
        "machine_code": machine_code,
        "enforcement_enabled": False,
    }


def _determine_change_type(existing: License, new_limits: dict, new_expires_at) -> tuple[str, str]:
    if new_expires_at and existing.expires_at and new_expires_at > existing.expires_at:
        return License.ChangeType.RENEWAL, "License renewed"
    upgrades = downgrades = 0
    for field, new_val in new_limits.items():
        old_val = getattr(existing, field, 0)
        if new_val > old_val:
            upgrades += 1
        elif new_val < old_val:
            downgrades += 1
    if upgrades and not downgrades:
        return License.ChangeType.UPGRADE, "Limits upgraded"
    if downgrades and not upgrades:
        return License.ChangeType.DOWNGRADE, "Limits downgraded"
    return License.ChangeType.RENEWAL, "License updated"


@transaction.atomic
def activate_license(
    *,
    organization: Organization,
    user,
    activation_code: str,
) -> tuple[License, str]:
    code = (activation_code or "").strip()
    if not code:
        raise ValueError("Activation code is required")

    machine_code = get_or_create_machine_code(organization=organization, user=user)

    if getattr(settings, "DEBUG", False) and code.upper() in ("DEV", "DEV-UNLIMITED", "DEVELOPMENT"):
        data = {
            "license_key": f"DEV-{secrets.token_hex(8).upper()}",
            "machine_code": machine_code,
            "limits": _dev_unlimited_limits(),
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
        }
        change_type = License.ChangeType.INITIAL
    else:
        data = verify_activation_code(code)
        if data["machine_code"] != machine_code:
            raise ValueError("Activation code is not for this machine")
        change_type = License.ChangeType.INITIAL

    license_key = data["license_key"]
    other = License.objects.filter(license_key=license_key).exclude(organization=organization).first()
    if other:
        raise ValueError("Activation code already used by another organization")

    limits = _map_limits(data.get("limits") or {})
    issued_at = datetime.fromisoformat(data["issued_at"].replace("Z", "+00:00"))
    expires_at = None
    if data.get("expires_at"):
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))

    existing = License.objects.filter(organization=organization).first()
    if existing:
        change_type, reason = _determine_change_type(existing, limits, expires_at)
        existing.archive_to_history(change_type=change_type, reason=reason, changed_by=user)
        existing.license_key = license_key
        existing.machine_code = machine_code
        existing.issued_at = issued_at
        existing.expires_at = expires_at
        existing.version += 1
        existing.change_type = change_type
        existing.change_reason = reason
        existing.status = License.Status.ACTIVE
        for field, val in limits.items():
            setattr(existing, field, val)
        existing.save()
        return existing, change_type

    lic = License.objects.create(
        organization=organization,
        license_key=license_key,
        machine_code=machine_code,
        issued_at=issued_at,
        expires_at=expires_at,
        activated_by=user if user and user.is_authenticated else None,
        signature=data.get("signature", ""),
        **limits,
    )
    lic.archive_to_history(change_type=License.ChangeType.INITIAL, reason="Initial activation", changed_by=user)
    return lic, License.ChangeType.INITIAL
