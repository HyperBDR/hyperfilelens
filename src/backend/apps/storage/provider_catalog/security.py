"""Endpoint and error-sanitization controls for cloud validation."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

from apps.storage.provider_catalog.errors import ProviderEndpointPolicyError


_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(access[_ -]?key(?:[_ -]?id)?|secret[_ -]?access[_ -]?key|authorization)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
    re.compile(r"(?i)(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)=[^\s]+"),
)


def sanitize_cloud_error(message: object, *, secrets: tuple[str, ...] = ()) -> str:
    text = str(message or "")
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = " ".join(text.split())
    return text[:1000] or "Cloud operation failed."


def validate_managed_endpoint_network(endpoint: str) -> None:
    """Resolve an already schema-validated endpoint and reject unsafe targets."""

    parsed = urlsplit(endpoint)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not hostname
    ):
        raise ProviderEndpointPolicyError(
            "ENDPOINT_POLICY_REJECTED",
            "Endpoint does not satisfy the managed Provider policy.",
        )

    try:
        addresses = socket.getaddrinfo(
            hostname,
            443,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except OSError as exc:
        raise ProviderEndpointPolicyError(
            "ENDPOINT_DNS_FAILED",
            "Endpoint DNS resolution failed.",
        ) from exc
    if not addresses:
        raise ProviderEndpointPolicyError(
            "ENDPOINT_DNS_FAILED",
            "Endpoint DNS resolution returned no addresses.",
        )
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address[4][0])
        except (IndexError, ValueError) as exc:
            raise ProviderEndpointPolicyError(
                "ENDPOINT_DNS_FAILED",
                "Endpoint DNS resolution returned an invalid address.",
            ) from exc
        if not ip.is_global:
            raise ProviderEndpointPolicyError(
                "ENDPOINT_PRIVATE_ADDRESS",
                "Endpoint resolves to an unauthorized network address.",
            )
