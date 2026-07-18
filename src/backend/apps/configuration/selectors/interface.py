"""
Configuration read API (platform-wide).

Other apps should call ``get_config`` here — not query ``GlobalConfig`` directly.
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

from apps.configuration.constants import NOT_FOUND
from apps.configuration.selectors.internal.cache import (
    bump_cache_version,
    entry_cache_key,
    get_cache_version,
    invalidate_entry,
)
from apps.configuration.selectors.internal.resolver import (
    resolve_global_value,
    resolve_tenant_value,
)
from apps.configuration.services.internal.registry import (
    ConfigKeySpec,
    all_key_specs,
)


def normalize_key(key: str) -> str:
    return str(key or "").strip()


def get_config(
    key: str,
    *,
    tenant_key: str | None = None,
    default: Any = None,
    use_cache: bool = True,
    cache_ttl_seconds: int | None = None,
) -> Any:
    """
    Resolve a config value: tenant override → global row → ``default``.

    Global values are cached under the global slot only (never under a tenant
    slot) so updating global does not leave stale data in per-tenant keys.
    """
    config_key = normalize_key(key)
    if not config_key:
        return default

    if cache_ttl_seconds is None:
        from apps.configuration.config import get_cache_ttl_seconds

        cache_ttl_seconds = get_cache_ttl_seconds()

    version = get_cache_version() if use_cache else 0

    if tenant_key:
        tenant = str(tenant_key).strip()
        if tenant:
            tenant_cache_key = entry_cache_key(
                version=version,
                config_key=config_key,
                tenant_key=tenant,
            )
            if use_cache:
                cached = cache.get(tenant_cache_key)
                if cached is not None:
                    return cached

            tenant_value = resolve_tenant_value(
                config_key=config_key,
                tenant_key=tenant,
            )
            if tenant_value is not NOT_FOUND:
                if use_cache:
                    cache.set(tenant_cache_key, tenant_value, cache_ttl_seconds)
                return tenant_value

    global_cache_key = entry_cache_key(
        version=version,
        config_key=config_key,
        tenant_key=None,
    )
    if use_cache:
        cached = cache.get(global_cache_key)
        if cached is not None:
            return cached

    global_value = resolve_global_value(config_key=config_key)
    if global_value is not NOT_FOUND:
        if use_cache:
            cache.set(global_cache_key, global_value, cache_ttl_seconds)
        return global_value

    return default


def list_registry_specs() -> tuple[ConfigKeySpec, ...]:
    """Known keys registered by domain apps (for admin UI / validation)."""
    return all_key_specs()


def invalidate_config_cache(
    key: str,
    *,
    tenant_key: str | None = None,
    scope: str | None = None,
) -> None:
    """Backward-compatible cache invalidation helper."""
    config_key = normalize_key(key)
    if not config_key:
        return
    if scope == "global" or (scope is None and not tenant_key):
        bump_cache_version()
        return
    if tenant_key:
        invalidate_entry(
            config_key=config_key,
            scope="tenant",
            tenant_key=str(tenant_key).strip(),
        )
