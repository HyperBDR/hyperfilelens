"""Stable fingerprint for alert de-duplication."""

from __future__ import annotations


def build_fingerprint(policy, resource_id, alert_key: str = "default") -> str:
    parts = [
        str(getattr(policy, "id", "")),
        str(getattr(policy, "organization_id", "")),
        str(resource_id or ""),
        str(alert_key or "default"),
    ]
    return "|".join(parts)
