"""Runtime storage configuration (GlobalConfig with app defaults)."""

from __future__ import annotations

from typing import Any

from apps.configuration.models import GlobalConfig
from apps.configuration.selectors.interface import get_config
from apps.storage import conf


def get_retention_config(*, tenant_key: str | None = None) -> dict[str, Any]:
    return get_config(
        conf.CONFIG_KEY_RETENTION,
        tenant_key=tenant_key,
        default=conf.DEFAULT_RETENTION,
    )


def get_filters_config(*, tenant_key: str | None = None) -> dict[str, Any]:
    return get_config(
        conf.CONFIG_KEY_FILTERS,
        tenant_key=tenant_key,
        default=conf.DEFAULT_FILTERS,
    )


def seed_global_config() -> None:
    """Insert global backup templates if missing (idempotent)."""
    seeds = (
        (
            conf.CONFIG_KEY_RETENTION,
            conf.DEFAULT_RETENTION,
            "Default GFS retention template",
        ),
        (
            conf.CONFIG_KEY_FILTERS,
            conf.DEFAULT_FILTERS,
            "Default include/exclude template",
        ),
    )
    for key, value, description in seeds:
        GlobalConfig.objects.get_or_create(
            key=key,
            scope=GlobalConfig.Scope.GLOBAL,
            tenant_key="",
            defaults={
                "value": value,
                "value_type": GlobalConfig.ValueType.OBJECT,
                "category": "backup",
                "description": description,
                "is_active": True,
            },
        )
