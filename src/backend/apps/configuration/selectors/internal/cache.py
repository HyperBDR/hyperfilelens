"""Cache keys and invalidation for configuration reads."""

from __future__ import annotations

from django.core.cache import cache

from apps.configuration.constants import CACHE_KEY_PREFIX, CACHE_VERSION_KEY
from apps.configuration.models import GlobalConfig


def get_cache_version() -> int:
    version = cache.get(CACHE_VERSION_KEY)
    if version is None:
        cache.set(CACHE_VERSION_KEY, 1, timeout=None)
        return 1
    return int(version)


def bump_cache_version() -> None:
    """Invalidate all cached entries (used when a global row changes)."""
    try:
        cache.incr(CACHE_VERSION_KEY)
    except ValueError:
        cache.set(CACHE_VERSION_KEY, 2, timeout=None)


def entry_cache_key(*, version: int, config_key: str, tenant_key: str | None) -> str:
    suffix = str(tenant_key).strip() if tenant_key else "-"
    return f"{CACHE_KEY_PREFIX}:v{version}:{suffix}:{config_key}"


def invalidate_entry(*, config_key: str, scope: str, tenant_key: str = "") -> None:
    """
    Drop cache for one logical key.

    Global changes bump the version so tenant fallbacks cannot serve stale globals.
    Tenant changes delete only that tenant's cache slot at the current version.
    """
    config_key = str(config_key or "").strip()
    if not config_key:
        return

    if scope == GlobalConfig.Scope.GLOBAL:
        bump_cache_version()
        return

    version = get_cache_version()
    tenant_key = str(tenant_key or "").strip()
    if tenant_key:
        cache.delete(
            entry_cache_key(
                version=version,
                config_key=config_key,
                tenant_key=tenant_key,
            ),
        )
