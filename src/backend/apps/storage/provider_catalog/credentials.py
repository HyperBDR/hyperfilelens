"""Encrypted, TTL-bound Redis credential storage for Provider validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from django.core.cache import cache

from apps.storage.conf import provider_validation_credential_ttl_seconds
from apps.storage.crypto import decrypt_text, encrypt_text
CREDENTIAL_CACHE_PREFIX = "storage:provider-validation:v1:credentials"


class ProviderCredentialUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ProviderCredentials:
    access_key_id: str
    secret_access_key: str


def _key(run_id: UUID | str) -> str:
    return f"{CREDENTIAL_CACHE_PREFIX}:{UUID(str(run_id))}"


def store_validation_credentials(
    run_id: UUID | str,
    credentials: ProviderCredentials,
) -> None:
    payload = json.dumps(
        {
            "access_key_id": credentials.access_key_id,
            "secret_access_key": credentials.secret_access_key,
        },
        separators=(",", ":"),
    )
    cache.set(
        _key(run_id),
        encrypt_text(payload),
        timeout=provider_validation_credential_ttl_seconds(),
    )


def load_validation_credentials(run_id: UUID | str) -> ProviderCredentials:
    token = cache.get(_key(run_id))
    if not isinstance(token, str) or not token:
        raise ProviderCredentialUnavailable(
            "Validation credentials are unavailable or have expired."
        )
    try:
        payload = json.loads(decrypt_text(token))
        access_key_id = str(payload["access_key_id"])
        secret_access_key = str(payload["secret_access_key"])
    except Exception as exc:
        delete_validation_credentials(run_id)
        raise ProviderCredentialUnavailable(
            "Validation credentials could not be decrypted."
        ) from exc
    if not access_key_id or not secret_access_key:
        raise ProviderCredentialUnavailable("Validation credentials are incomplete.")
    return ProviderCredentials(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )


def delete_validation_credentials(run_id: UUID | str) -> None:
    cache.delete(_key(run_id))
