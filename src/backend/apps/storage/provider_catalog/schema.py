"""Schema validation, normalization, and RFC 8785 checksums."""

from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from apps.storage.conf import provider_catalog_limits
from apps.storage.provider_catalog.errors import ProviderCatalogValidationError
from apps.storage.provider_catalog.resources import (
    SCHEMA_RESOURCE,
    read_packaged_resource,
)


CURRENT_SCHEMA_VERSION = 1
RESERVED_PROVIDER_IDS = frozenset({"custom", "other"})


def _issue(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path or "$", "code": code, "message": message}


def _raise(path: str, code: str, message: str) -> None:
    raise ProviderCatalogValidationError(
        message,
        issues=[_issue(path, code, message)],
    )


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    schema = json.loads(read_packaged_resource(SCHEMA_RESOURCE).decode("utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _reject_float(value: str) -> None:
    raise ValueError(f"floating-point number {value!r} is not allowed")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite number {value!r} is not allowed")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _exceeds_json_depth(value: Any, limit: int) -> bool:
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if depth > limit:
            return True
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return False


def _reject_invalid_unicode(value: Any) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            _raise("$", "invalid_unicode", "Catalog contains invalid Unicode.")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_invalid_unicode(key)
            _reject_invalid_unicode(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_invalid_unicode(item)


def parse_catalog(raw: str | bytes) -> dict[str, Any]:
    limits = provider_catalog_limits()
    if isinstance(raw, str):
        try:
            raw_bytes = raw.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            _raise("$", "invalid_utf8", "Catalog must be valid UTF-8.")
    elif isinstance(raw, bytes):
        raw_bytes = raw
    else:
        _raise("$", "invalid_type", "Catalog content must be a UTF-8 JSON string.")

    if len(raw_bytes) > limits["max_bytes"]:
        _raise(
            "$",
            "resource_limit",
            f"Catalog exceeds the {limits['max_bytes']} byte limit.",
        )
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _raise("$", "invalid_utf8", "Catalog must be valid UTF-8.")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (ValueError, json.JSONDecodeError, RecursionError) as exc:
        line = getattr(exc, "lineno", None)
        column = getattr(exc, "colno", None)
        location = f" at line {line}, column {column}" if line and column else ""
        _raise("$", "invalid_json", f"Invalid JSON{location}.")

    if _exceeds_json_depth(value, limits["max_depth"]):
        _raise(
            "$",
            "resource_limit",
            f"Catalog exceeds the nesting depth limit of {limits['max_depth']}.",
        )
    _reject_invalid_unicode(value)
    return normalize_catalog(value)


def _trim_known_strings(value: Any) -> Any:
    normalized = copy.deepcopy(value)
    if not isinstance(normalized, dict):
        return normalized
    providers = normalized.get("providers")
    if not isinstance(providers, list):
        return normalized
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        if isinstance(provider.get("display_name"), str):
            provider["display_name"] = provider["display_name"].strip()
        regions = provider.get("regions")
        if not isinstance(regions, list):
            continue
        for region in regions:
            if not isinstance(region, dict):
                continue
            for field in (
                "id",
                "display_name",
                "region_group",
                "region_group_en",
                "external_endpoint",
                "internal_endpoint",
            ):
                if isinstance(region.get(field), str):
                    region[field] = region[field].strip()
    return normalized


def _path_from_jsonschema(error) -> str:
    parts: list[str] = []
    for item in error.absolute_path:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            parts.append(("." if parts else "") + str(item))
    return (
        "$" + ("." if parts and not parts[0].startswith("[") else "") + "".join(parts)
    )


def _normalize_endpoint(endpoint: str, *, path: str) -> str:
    if "://" in endpoint:
        _raise(path, "invalid_endpoint", "Endpoint must be a hostname without a URL scheme.")
    try:
        parsed = urlsplit(f"https://{endpoint}")
        port = parsed.port
    except ValueError:
        _raise(path, "invalid_endpoint", "Endpoint is not a valid hostname.")
    if not parsed.netloc or not parsed.hostname:
        _raise(path, "invalid_endpoint", "Endpoint must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        _raise(path, "invalid_endpoint", "Endpoint credentials are not allowed.")
    if parsed.path or parsed.query or parsed.fragment:
        _raise(
            path,
            "invalid_endpoint",
            "Endpoint path, query, and fragment are not allowed.",
        )
    if port not in (None, 443):
        _raise(path, "invalid_endpoint", "Endpoint port is not allowed.")

    hostname = parsed.hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return hostname
    _raise(path, "invalid_endpoint", "Endpoint must be a DNS hostname, not an IP address.")


def normalize_catalog(value: Any) -> dict[str, Any]:
    normalized = _trim_known_strings(value)
    errors = sorted(
        _schema_validator().iter_errors(normalized),
        key=lambda item: tuple(str(part) for part in item.path),
    )
    if errors:
        issues = [
            _issue(_path_from_jsonschema(error), "schema", error.message)
            for error in errors[:50]
        ]
        raise ProviderCatalogValidationError(
            "Catalog does not match schema version 1.",
            issues=issues,
        )

    limits = provider_catalog_limits()
    providers = normalized["providers"]
    if len(providers) > limits["max_providers"]:
        _raise(
            "$.providers",
            "resource_limit",
            f"Catalog exceeds the Provider limit of {limits['max_providers']}.",
        )

    provider_ids: set[str] = set()
    for provider_index, provider in enumerate(providers):
        provider_path = f"$.providers[{provider_index}]"
        provider_id = provider["id"]
        if provider_id in provider_ids:
            _raise(
                f"{provider_path}.id",
                "duplicate_provider",
                f"Duplicate Provider ID {provider_id!r}.",
            )
        provider_ids.add(provider_id)
        if provider_id in RESERVED_PROVIDER_IDS:
            _raise(
                f"{provider_path}.id",
                "reserved_provider",
                f"Provider ID {provider_id!r} is reserved.",
            )
        regions = provider["regions"]
        if len(regions) > limits["max_regions"]:
            _raise(
                f"{provider_path}.regions",
                "resource_limit",
                f"Provider exceeds the region limit of {limits['max_regions']}.",
            )
        if provider["enabled"] and not regions:
            _raise(
                f"{provider_path}.regions",
                "empty_regions",
                "An enabled Provider must contain at least one region.",
            )
        region_ids: set[str] = set()
        external_endpoints: set[str] = set()
        internal_endpoints: set[str] = set()
        for region_index, region in enumerate(regions):
            region_path = f"{provider_path}.regions[{region_index}]"
            if region["id"] in region_ids:
                _raise(
                    f"{region_path}.id",
                    "duplicate_region",
                    f"Duplicate region ID {region['id']!r}.",
                )
            region["external_endpoint"] = _normalize_endpoint(
                region["external_endpoint"],
                path=f"{region_path}.external_endpoint",
            )
            region["internal_endpoint"] = _normalize_endpoint(
                region["internal_endpoint"],
                path=f"{region_path}.internal_endpoint",
            )
            if region["external_endpoint"] in external_endpoints:
                _raise(
                    f"{region_path}.external_endpoint",
                    "duplicate_external_endpoint",
                    f"Duplicate external Endpoint {region['external_endpoint']!r}.",
                )
            if region["internal_endpoint"] in internal_endpoints:
                _raise(
                    f"{region_path}.internal_endpoint",
                    "duplicate_internal_endpoint",
                    f"Duplicate internal Endpoint {region['internal_endpoint']!r}.",
                )
            region_ids.add(region["id"])
            external_endpoints.add(region["external_endpoint"])
            internal_endpoints.add(region["internal_endpoint"])
        # Array order is part of the Catalog's presentation contract. The
        # repository UI preserves Provider order, region-group first
        # appearance, and Region order exactly as configured.
        provider["regions"] = regions

    normalized["providers"] = providers
    return normalized


def normalize_provider(
    provider: dict[str, Any], *, schema_version: int = 1
) -> dict[str, Any]:
    catalog = normalize_catalog(
        {"schema_version": schema_version, "providers": [provider]}
    )
    return catalog["providers"][0]


def canonical_json_bytes(value: Any) -> bytes:
    """Return RFC 8785 bytes for values admitted by the v1 schema.

    The schema contains only strings, booleans, arrays, objects, and the integer
    schema version. For that restricted value set, these JSON encoder settings
    are the JSON Canonicalization Scheme representation.
    """

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def checksum_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def provider_checksum(provider: dict[str, Any], *, schema_version: int = 1) -> str:
    normalized = normalize_provider(provider, schema_version=schema_version)
    return checksum_json({"schema_version": schema_version, "provider": normalized})


def catalog_checksum(catalog: dict[str, Any]) -> str:
    return checksum_json(normalize_catalog(catalog))
