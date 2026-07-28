from __future__ import annotations

from typing import Any


S3_ENDPOINT_EXTERNAL = "external"
S3_ENDPOINT_INTERNAL = "internal"
S3_ENDPOINT_TYPES = frozenset({S3_ENDPOINT_EXTERNAL, S3_ENDPOINT_INTERNAL})


def normalize_s3_endpoint_host(value: object) -> str:
    raw = str(value or "").strip()
    if raw.lower().startswith("https://"):
        raw = raw[8:]
    elif raw.lower().startswith("http://"):
        raw = raw[7:]
    return raw.strip().rstrip("/").lower().rstrip(".")


def s3_endpoint_snapshot(
    *,
    external_endpoint: object,
    internal_endpoint: object,
    endpoint_type: object = S3_ENDPOINT_EXTERNAL,
) -> dict[str, str]:
    external = normalize_s3_endpoint_host(external_endpoint)
    internal = normalize_s3_endpoint_host(internal_endpoint) or external
    requested_type = str(endpoint_type or S3_ENDPOINT_EXTERNAL).strip().lower()
    if requested_type not in S3_ENDPOINT_TYPES:
        raise ValueError("Endpoint type must be external or internal.")
    if not external:
        raise ValueError("External Endpoint is required.")
    if external == internal:
        requested_type = S3_ENDPOINT_EXTERNAL
    endpoint = internal if requested_type == S3_ENDPOINT_INTERNAL else external
    return {
        "endpoint_type": requested_type,
        "endpoint": endpoint,
        "external_endpoint": external,
        "internal_endpoint": internal,
    }


def compact_s3_repository_endpoints(
    config: dict[str, Any] | None,
    *,
    s3_platform: object,
    external_endpoint: object = None,
    internal_endpoint: object = None,
) -> dict[str, Any]:
    """Return the canonical persisted Endpoint representation for an S3 repository.

    ``endpoint`` is always the control/default data Endpoint.  Managed Providers
    retain the external/internal pair only when it represents a real routing
    choice.  Custom S3 repositories never expose a second route.
    """

    value = dict(config) if isinstance(config, dict) else {}
    external = normalize_s3_endpoint_host(
        external_endpoint
        if external_endpoint is not None
        else value.get("endpoint") or value.get("external_endpoint")
    )
    internal = normalize_s3_endpoint_host(
        internal_endpoint
        if internal_endpoint is not None
        else value.get("internal_endpoint")
    ) or external
    if not external:
        raise ValueError("External Endpoint is required.")

    value["endpoint"] = external
    value.pop("endpoint_type", None)
    value.pop("external_endpoint", None)
    value.pop("internal_endpoint", None)

    platform = str(s3_platform or "").strip().lower()
    if platform != "custom" and internal != external:
        value["external_endpoint"] = external
        value["internal_endpoint"] = internal
    return value


def repository_data_endpoint(
    config: dict[str, Any] | None,
    *,
    endpoint_type: object = S3_ENDPOINT_EXTERNAL,
    endpoint: object = None,
) -> str:
    value = config if isinstance(config, dict) else {}
    snapshotted_endpoint = normalize_s3_endpoint_host(endpoint)
    if snapshotted_endpoint:
        return snapshotted_endpoint
    external = value.get("endpoint") or value.get("external_endpoint")
    requested_type = str(endpoint_type or S3_ENDPOINT_EXTERNAL).strip().lower()
    if requested_type == S3_ENDPOINT_INTERNAL:
        internal = normalize_s3_endpoint_host(value.get("internal_endpoint"))
        normalized_external = normalize_s3_endpoint_host(external)
        if not internal or internal == normalized_external:
            raise ValueError("Internal Endpoint is not available for this repository.")
    else:
        internal = value.get("internal_endpoint") or external
    return s3_endpoint_snapshot(
        external_endpoint=external,
        internal_endpoint=internal,
        endpoint_type=endpoint_type,
    )["endpoint"]


def repository_control_endpoint(config: dict[str, Any] | None) -> str:
    value = config if isinstance(config, dict) else {}
    return normalize_s3_endpoint_host(
        value.get("endpoint") or value.get("external_endpoint")
    )
