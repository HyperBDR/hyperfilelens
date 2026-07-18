"""Bulk operations for alert policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.alert.models import AlertPolicy


@dataclass
class _BulkFailure:
    id: str
    reason: str


def _bulk_failure_dicts(failures: list[_BulkFailure]) -> list[dict[str, Any]]:
    return [asdict(f) for f in failures]


def _unique_uuid_strings(ids: list[UUID]) -> list[str]:
    unique_ids: list[str] = []
    seen: set[str] = set()
    for raw in ids:
        value = str(raw)
        if value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)
    return unique_ids


def bulk_set_policy_state(
    *,
    organization_id: int,
    ids: list[UUID],
    enabled: bool,
) -> dict[str, Any]:
    """Enable or disable policies scoped to the caller's organisation."""
    if not ids:
        return {"updated": [], "failed": []}

    unique_ids = _unique_uuid_strings(ids)
    existing = list(
        AlertPolicy.objects.filter(
            organization_id=organization_id,
            id__in=unique_ids,
        )
    )
    by_id = {str(policy.id): policy for policy in existing}
    failed: list[_BulkFailure] = [
        _BulkFailure(id=policy_id, reason="not_found")
        for policy_id in unique_ids
        if policy_id not in by_id
    ]

    updated: list[str] = []
    with transaction.atomic():
        for policy in existing:
            policy_id = str(policy.id)
            if policy.enabled == enabled:
                updated.append(policy_id)
                continue
            policy.enabled = enabled
            policy.save(update_fields=["enabled", "updated_at"])
            updated.append(policy_id)
    return {"updated": updated, "failed": _bulk_failure_dicts(failed)}


def bulk_delete_policies(
    *,
    organization_id: int,
    ids: list[UUID],
) -> dict[str, Any]:
    """Delete policies scoped to the caller's organisation."""
    if not ids:
        return {"deleted": [], "failed": []}

    unique_ids = _unique_uuid_strings(ids)
    existing = list(
        AlertPolicy.objects.filter(
            organization_id=organization_id,
            id__in=unique_ids,
        )
    )
    by_id = {str(policy.id): policy for policy in existing}
    failed: list[_BulkFailure] = [
        _BulkFailure(id=policy_id, reason="not_found")
        for policy_id in unique_ids
        if policy_id not in by_id
    ]

    deleted: list[str] = []
    with transaction.atomic():
        for policy in existing:
            policy_id = str(policy.id)
            policy.delete()
            deleted.append(policy_id)
    return {"deleted": deleted, "failed": _bulk_failure_dicts(failed)}
