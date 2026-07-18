"""
Configuration write API (admin / management plane).
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from apps.configuration.models import GlobalConfig
from apps.configuration.selectors.internal.cache import invalidate_entry
from apps.configuration.services.internal.validation import (
    validate_config_key,
    validate_value_for_type,
)


def save_global_config(
    *,
    user: AbstractBaseUser,
    key: str,
    value: Any,
    value_type: str,
    category: str = "",
    description: str = "",
    is_active: bool = True,
) -> GlobalConfig:
    validate_config_key(key)
    validate_value_for_type(value=value, value_type=value_type)

    row, _created = GlobalConfig.objects.update_or_create(
        key=key.strip(),
        scope=GlobalConfig.Scope.GLOBAL,
        tenant_key="",
        defaults={
            "value": value,
            "value_type": value_type,
            "category": category,
            "description": description,
            "is_active": is_active,
            "updated_by": user,
        },
    )
    if _created:
        row.created_by = user
        row.save(update_fields=["created_by"])
    invalidate_entry(
        config_key=row.key,
        scope=GlobalConfig.Scope.GLOBAL,
    )
    return row


def delete_global_config(*, key: str) -> None:
    GlobalConfig.objects.filter(
        key=key.strip(),
        scope=GlobalConfig.Scope.GLOBAL,
        tenant_key="",
    ).delete()
    invalidate_entry(config_key=key, scope=GlobalConfig.Scope.GLOBAL)
