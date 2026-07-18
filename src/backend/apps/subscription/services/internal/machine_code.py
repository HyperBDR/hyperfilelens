"""Machine code generation for organization binding."""

from __future__ import annotations

import hashlib
import platform
import uuid


def generate_machine_code(*, organization_id: int, user_id: int) -> tuple[str, dict]:
    host = platform.node() or "unknown"
    seed = f"org:{organization_id}:user:{user_id}:host:{host}"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:32].upper()
    code = f"HFL-MCH-{digest[0:8]}-{digest[8:16]}-{digest[16:24]}-{digest[24:32]}"
    return code, {"hostname": host, "source": "platform"}


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None
