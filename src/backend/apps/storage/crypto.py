"""
Encryption helpers for credential storage.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    raw = os.getenv("STORAGE_ENCRYPTION_KEY") or os.getenv("SECRET_KEY", "")
    if not raw:
        raw = "dev-only-change-me"
    return Fernet(_derive_key(raw))


def encrypt_text(value: str) -> str:
    if value is None:
        return ""
    token = get_fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str) -> str:
    if not token:
        return ""
    out = get_fernet().decrypt(token.encode("utf-8"))
    return out.decode("utf-8")

