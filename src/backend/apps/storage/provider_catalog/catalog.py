"""Default/override resolution for the effective Provider Catalog."""

from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from apps.storage.provider_catalog.errors import ProviderCatalogValidationError
from apps.storage.provider_catalog.models import StorageProviderOverride
from apps.storage.provider_catalog.resources import (
    DEFAULT_CATALOG_RESOURCE,
    read_packaged_resource,
)
from apps.storage.provider_catalog.schema import (
    CURRENT_SCHEMA_VERSION,
    normalize_provider,
    parse_catalog,
    provider_checksum,
)


@lru_cache(maxsize=1)
def load_default_catalog() -> dict[str, Any]:
    try:
        return parse_catalog(read_packaged_resource(DEFAULT_CATALOG_RESOURCE))
    except ProviderCatalogValidationError as exc:
        raise ImproperlyConfigured(
            "The packaged Object Storage Provider Catalog is invalid."
        ) from exc


def _provider_record(
    *,
    config: dict[str, Any],
    schema_version: int,
    source: str,
    checksum: str,
    updated_at: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "config": config,
        "source": source,
        "checksum": checksum,
        "updated_at": updated_at,
    }


def default_provider_records() -> dict[str, dict[str, Any]]:
    catalog = load_default_catalog()
    version = catalog["schema_version"]
    return {
        provider["id"]: _provider_record(
            config=copy.deepcopy(provider),
            schema_version=version,
            source="default",
            checksum=provider_checksum(provider, schema_version=version),
            updated_at=None,
        )
        for provider in catalog["providers"]
    }


def _load_effective_records() -> dict[str, dict[str, Any]]:
    records = default_provider_records()
    for override in StorageProviderOverride.objects.all().order_by("provider_id"):
        if override.schema_version != CURRENT_SCHEMA_VERSION:
            raise ImproperlyConfigured(
                f"Provider override {override.provider_id!r} uses an unsupported schema version."
            )
        try:
            config = normalize_provider(
                override.config,
                schema_version=override.schema_version,
            )
        except ProviderCatalogValidationError as exc:
            raise ImproperlyConfigured(
                f"Provider override {override.provider_id!r} is invalid."
            ) from exc
        checksum = provider_checksum(config, schema_version=override.schema_version)
        if config["id"] != override.provider_id or checksum != override.checksum:
            raise ImproperlyConfigured(
                f"Provider override {override.provider_id!r} failed its integrity check."
            )
        records[override.provider_id] = _provider_record(
            config=config,
            schema_version=override.schema_version,
            source="override",
            checksum=checksum,
            updated_at=override.updated_at.isoformat(),
        )
    # Replacing an existing key retains its default Catalog position. New
    # override-only Providers are appended in the stable database order above.
    return records


def effective_provider_records() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(_load_effective_records())


def effective_catalog() -> dict[str, Any]:
    records = effective_provider_records()
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "providers": [record["config"] for record in records.values()],
    }


def effective_provider(provider_id: str) -> dict[str, Any] | None:
    record = effective_provider_records().get(provider_id)
    return copy.deepcopy(record) if record else None
