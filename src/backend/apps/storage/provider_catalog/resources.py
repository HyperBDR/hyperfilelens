"""Single packaged-resource entry point for Provider Catalog data."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files


RESOURCE_PACKAGE = "apps.storage.provider_catalog.data"
DEFAULT_CATALOG_RESOURCE = "default_provider_catalog.json"
SCHEMA_RESOURCE = "provider_catalog.schema.json"


@lru_cache(maxsize=2)
def read_packaged_resource(name: str) -> bytes:
    if name not in {
        DEFAULT_CATALOG_RESOURCE,
        SCHEMA_RESOURCE,
    }:
        raise ValueError("Unknown Provider Catalog resource.")
    return files(RESOURCE_PACKAGE).joinpath(name).read_bytes()
