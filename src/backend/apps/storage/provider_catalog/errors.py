"""Provider Catalog domain errors."""

from __future__ import annotations


class ProviderCatalogError(Exception):
    code = "PROVIDER_CATALOG_ERROR"

    def __init__(self, message: str, *, issues: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.issues = issues or []


class ProviderCatalogValidationError(ProviderCatalogError):
    code = "PROVIDER_CATALOG_INVALID"


class ProviderCatalogConflictError(ProviderCatalogError):
    code = "PROVIDER_CATALOG_CONFLICT"


class ProviderEndpointPolicyError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
