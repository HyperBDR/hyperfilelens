"""
License quota facade.

During development QUOTA_ENFORCEMENT_ENABLED is False — all checks pass.
"""

from __future__ import annotations

from apps.subscription.constants import QUOTA_ENFORCEMENT_ENABLED


def enforce_license_quota(organization, resource_type: str, additional: int = 1):
    """No-op while enforcement is disabled."""
    if not QUOTA_ENFORCEMENT_ENABLED:
        return None
    # Future: load org license and raise PermissionDenied when exceeded.
    return None


def validate_quota(organization, quota_type: str, amount: int = 1) -> dict:
    """Always allow during development."""
    if not QUOTA_ENFORCEMENT_ENABLED:
        return {
            "is_valid": True,
            "quota_type": quota_type,
            "message": "Quota enforcement disabled in development",
            "enforcement_enabled": False,
        }
    return {
        "is_valid": True,
        "quota_type": quota_type,
        "enforcement_enabled": True,
    }
