from __future__ import annotations

import json
from typing import Any

from apps.storage.crypto import decrypt_text, encrypt_text


ENVELOPE_KEY = "_secret_envelope"
SECRET_KEYS = frozenset(
    {
        "password",
        "secret_key",
        "secret_access_key",
        "access_token",
        "private_key",
        "secret",
        "token",
    }
)
PUBLIC_HINT_KEYS = frozenset({"username", "domain"})


def protect_source_credentials(credentials: dict | None) -> dict:
    """Return a database-safe representation with secret values encrypted."""
    payload = dict(credentials or {})
    if ENVELOPE_KEY in payload:
        return payload

    public = {key: value for key, value in payload.items() if key not in SECRET_KEYS}
    secrets = {key: value for key, value in payload.items() if key in SECRET_KEYS}
    if secrets:
        plaintext = json.dumps(
            secrets,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        public[ENVELOPE_KEY] = {
            "alg": "fernet-json-v1",
            "key_version": "v1",
            "ciphertext": encrypt_text(plaintext),
        }
    return public


def resolve_source_credentials(stored: dict | None) -> dict:
    """Resolve encrypted credentials, while accepting pre-migration plaintext rows."""
    payload = dict(stored or {})
    envelope = payload.pop(ENVELOPE_KEY, None)
    if not isinstance(envelope, dict):
        return payload
    ciphertext = str(envelope.get("ciphertext") or "")
    if not ciphertext:
        return payload
    plaintext = decrypt_text(ciphertext)
    decoded = json.loads(plaintext)
    if not isinstance(decoded, dict):
        raise ValueError("Source credential payload is invalid.")
    payload.update(decoded)
    return payload


def merge_source_credentials(stored: dict | None, incoming: dict | None) -> dict:
    """Preserve saved secrets when an update omits or blanks a secret field."""
    merged = resolve_source_credentials(stored)
    for key, value in dict(incoming or {}).items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def source_credential_hint(stored: dict | None) -> dict[str, Any]:
    """Build the only credential shape that may be returned by source APIs."""
    resolved = resolve_source_credentials(stored)
    hint: dict[str, Any] = {
        key: resolved[key]
        for key in PUBLIC_HINT_KEYS
        if resolved.get(key) not in (None, "")
    }
    hint["has_password"] = bool(resolved.get("password"))
    hint["has_secret_key"] = bool(
        resolved.get("secret_key") or resolved.get("secret_access_key")
    )
    return hint


def scrub_source_secrets(value: Any) -> Any:
    """Recursively remove credential-shaped values from API and task payloads."""
    if isinstance(value, dict):
        return {
            key: scrub_source_secrets(item)
            for key, item in value.items()
            if str(key).lower() not in SECRET_KEYS and key != ENVELOPE_KEY
        }
    if isinstance(value, list):
        return [scrub_source_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [scrub_source_secrets(item) for item in value]
    return value
