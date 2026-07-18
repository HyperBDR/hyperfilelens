"""Activation code crypto (compatible with xxz HFL-ACT format)."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

LICENSE_SECRET_KEY = "HFL_LICENSE_SECRET_2024_DO_NOT_SHARE"


def generate_activation_code(
    *,
    license_key: str,
    machine_code: str,
    limits: dict[str, int],
    validity_days: int = 365,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=validity_days)
    data = {
        "license_key": license_key,
        "machine_code": machine_code,
        "limits": limits,
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    data_str = json.dumps(data, sort_keys=True)
    data["signature"] = hashlib.sha256((data_str + LICENSE_SECRET_KEY).encode()).hexdigest()
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    return f"HFL-ACT-{encoded}"


def verify_activation_code(activation_code: str) -> dict[str, Any]:
    if not activation_code.startswith("HFL-ACT-"):
        raise ValueError("Invalid activation code format")
    encoded = activation_code[8:]
    data = json.loads(base64.b64decode(encoded).decode())
    stored_signature = data.pop("signature", None)
    if not stored_signature:
        raise ValueError("Missing signature")
    data_str = json.dumps(data, sort_keys=True)
    expected = hashlib.sha256((data_str + LICENSE_SECRET_KEY).encode()).hexdigest()
    if stored_signature != expected:
        raise ValueError("Invalid signature")
    if data.get("expires_at"):
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            raise ValueError("Activation code expired")
    return data
