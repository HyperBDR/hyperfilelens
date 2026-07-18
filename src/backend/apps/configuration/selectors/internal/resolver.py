"""Database resolution for configuration keys."""

from __future__ import annotations

from typing import Any

from apps.configuration.constants import NOT_FOUND
from apps.configuration.models import GlobalConfig


def resolve_tenant_value(*, config_key: str, tenant_key: str) -> Any:
    row = (
        GlobalConfig.objects.filter(
            key=config_key,
            is_active=True,
            scope=GlobalConfig.Scope.TENANT,
            tenant_key=tenant_key,
        )
        .only("value")
        .first()
    )
    if row is None:
        return NOT_FOUND
    return row.value


def resolve_global_value(*, config_key: str) -> Any:
    row = (
        GlobalConfig.objects.filter(
            key=config_key,
            is_active=True,
            scope=GlobalConfig.Scope.GLOBAL,
            tenant_key="",
        )
        .only("value")
        .first()
    )
    if row is None:
        return NOT_FOUND
    return row.value
