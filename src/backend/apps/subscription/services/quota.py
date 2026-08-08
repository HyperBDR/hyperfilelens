"""
Host quota facade.

Create-path helpers live here; hard checks run through QuotaProvider (plugin).
Community (empty socket): no-op unless a future community hard-limit is enabled.
"""

from __future__ import annotations

from apps.subscription.constants import QUOTA_ENFORCEMENT_ENABLED, UNLIMITED
from common.errors import AppError
from common.extension_spi import get_quota_provider

_QUOTA_FULL_MESSAGE = (
    "Organization quota is full. Contact your platform administrator to raise limits."
)

_NODE_ROLE_TO_RESOURCE = {
    "agent": "max_source_hosts",
    "proxy": "max_proxies",
    "gateway": "max_gateways",
}

_REPO_TYPE_TO_RESOURCE = {
    "s3": "max_object_storage",
    "nas": "max_target_nas",
    "proxy_fs": "max_standalone_disk",
}


def _enforcement_flag_enabled() -> bool:
    try:
        from django.conf import settings

        return bool(getattr(settings, "HFL_QUOTA_ENFORCEMENT_ENABLED", QUOTA_ENFORCEMENT_ENABLED))
    except Exception:
        return bool(QUOTA_ENFORCEMENT_ENABLED)


def _quota_exceeded_error(
    *,
    quota_type: str,
    limit: int | float,
    used: int | float,
    requested: int | float = 0,
) -> AppError:
    return AppError(
        code="SUBSCRIPTION.QUOTA_EXCEEDED",
        status=403,
        title=_QUOTA_FULL_MESSAGE,
        diagnostic=_QUOTA_FULL_MESSAGE,
        meta={
            "quota_type": quota_type,
            "limit": limit,
            "used": used,
            "requested": requested,
        },
    )


def enforce_license_quota(organization, resource_type: str, additional: int | float = 1):
    """Deny path for new consumption when over quota (hard limit)."""
    provider = get_quota_provider()
    if provider is not None:
        return provider.check_quota(organization, resource_type, additional)
    if not _enforcement_flag_enabled():
        return None
    return None


def enforce_node_role_quota(*, organization, role: str):
    resource = _NODE_ROLE_TO_RESOURCE.get(str(role or "").strip().lower())
    if not resource:
        return None
    return enforce_license_quota(organization, resource, additional=1)


def enforce_repository_type_quota(*, organization, repo_type: str):
    resource = _REPO_TYPE_TO_RESOURCE.get(str(repo_type or "").strip().lower())
    if not resource:
        return None
    return enforce_license_quota(organization, resource, additional=1)


def assert_gateway_select_within_limits(
    *,
    organization,
    file_count: int,
    size_bytes: int,
    unknown_directory: bool = False,
) -> None:
    """
    Gateway/copilot selection caps.

    When a plugin provides get_limits, finite caps always apply (not gated on
    create-path enforcement). Without a provider, this is a no-op.
    """
    provider = get_quota_provider()
    if provider is None or not hasattr(provider, "get_limits"):
        return None
    limits = provider.get_limits(organization) or {}
    max_files = int(limits.get("gateway_select_max_files", UNLIMITED))
    max_bytes = int(limits.get("gateway_select_max_bytes", UNLIMITED))
    if unknown_directory and (max_files >= 0 or max_bytes >= 0):
        raise _quota_exceeded_error(
            quota_type="gateway_select_max_files",
            limit=max_files if max_files >= 0 else max_bytes,
            used=0,
            requested=file_count,
        )
    if max_files >= 0 and int(file_count) > max_files:
        raise _quota_exceeded_error(
            quota_type="gateway_select_max_files",
            limit=max_files,
            used=int(file_count),
            requested=0,
        )
    if max_bytes >= 0 and int(size_bytes) > max_bytes:
        raise _quota_exceeded_error(
            quota_type="gateway_select_max_bytes",
            limit=max_bytes,
            used=int(size_bytes),
            requested=0,
        )
    return None


def validate_quota(organization, quota_type: str, amount: int = 1) -> dict:
    """Preview whether a quota check would pass."""
    provider = get_quota_provider()
    if provider is not None and hasattr(provider, "validate_quota"):
        return provider.validate_quota(organization, quota_type, amount)
    # Host alone never hard-enforces; do not claim enforcement_enabled=True.
    return {
        "is_valid": True,
        "quota_type": quota_type,
        "message": (
            "Quota enforcement disabled"
            if not _enforcement_flag_enabled()
            else "No QuotaProvider; Host create-path enforcement is a no-op"
        ),
        "enforcement_enabled": False,
    }
