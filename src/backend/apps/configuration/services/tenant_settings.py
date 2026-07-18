"""Tenant organization settings (Configuration → System Settings)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from apps.configuration.models import GlobalConfig
from apps.configuration.selectors.interface import get_config, invalidate_config_cache
from apps.configuration.services.internal.registry import registry_by_key
from apps.configuration.services.internal.validation import (
    validate_config_key,
    validate_value_for_type,
)
from apps.configuration.tenant_conf import (
    CONFIG_KEY_DR_TASK_CONCURRENCY,
    DEFAULT_DR_TASK_CONCURRENCY,
)


@dataclass(frozen=True)
class TenantOrgSettingSpec:
    key: str
    category: str
    value_type: str
    default: Any
    description: str = ""


def tenant_org_setting_specs() -> tuple[TenantOrgSettingSpec, ...]:
    return (
        TenantOrgSettingSpec(
            key=CONFIG_KEY_DR_TASK_CONCURRENCY,
            category="file_dr",
            value_type=GlobalConfig.ValueType.NUMBER,
            default=DEFAULT_DR_TASK_CONCURRENCY,
            description="Max concurrent data protection tasks for this organization.",
        ),
    )


def _spec_by_key() -> dict[str, TenantOrgSettingSpec]:
    return {spec.key: spec for spec in tenant_org_setting_specs()}


def _tenant_row(*, org_key: str, key: str) -> GlobalConfig | None:
    return GlobalConfig.objects.filter(
        key=key,
        scope=GlobalConfig.Scope.TENANT,
        tenant_key=org_key,
        is_active=True,
    ).first()


def list_org_settings(*, org_key: str) -> list[dict]:
    org_key = str(org_key or "").strip()
    rows: list[dict] = []
    for spec in tenant_org_setting_specs():
        tenant_row = _tenant_row(org_key=org_key, key=spec.key)
        effective = get_config(spec.key, tenant_key=org_key, default=spec.default)
        if tenant_row is not None:
            source = "tenant"
        elif GlobalConfig.objects.filter(
            key=spec.key,
            scope=GlobalConfig.Scope.GLOBAL,
            tenant_key="",
            is_active=True,
        ).exists():
            source = "global"
        else:
            source = "default"
        rows.append(
            {
                "key": spec.key,
                "category": spec.category,
                "value_type": spec.value_type,
                "value": effective,
                "effective_value": effective,
                "value_source": source,
                "id": tenant_row.id if tenant_row else None,
                "has_tenant_override": tenant_row is not None,
            }
        )
    return rows


@transaction.atomic
def upsert_org_settings(
    *,
    org_key: str,
    user: AbstractBaseUser,
    items: list[dict],
) -> list[dict]:
    org_key = str(org_key or "").strip()
    if not org_key:
        raise ValueError("organization key is required")

    specs = _spec_by_key()
    for item in items:
        key = str(item.get("key") or "").strip()
        if key not in specs:
            raise ValueError(f"setting not allowed for tenant: {key}")
        spec = specs[key]
        value = item.get("value")
        validate_config_key(key)
        validate_value_for_type(value=value, value_type=spec.value_type)

        registry = registry_by_key().get(key)
        category = spec.category
        if registry:
            category = registry.category

        row, created = GlobalConfig.objects.update_or_create(
            key=key,
            scope=GlobalConfig.Scope.TENANT,
            tenant_key=org_key,
            defaults={
                "value": value,
                "value_type": spec.value_type,
                "category": category,
                "description": spec.description,
                "is_active": True,
                "updated_by": user,
            },
        )
        if created:
            row.created_by = user
            row.save(update_fields=["created_by"])
        invalidate_config_cache(key=key, tenant_key=org_key, scope="tenant")

    return list_org_settings(org_key=org_key)
