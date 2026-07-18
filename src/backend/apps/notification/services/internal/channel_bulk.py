"""Bulk operations for notification channels.

Mirrors the style of ``apps.protection.services.interface.bulk_*`` so that
the API view layer can stay thin: validate ids + org, then return a dict
listing what changed and what failed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from django.db import transaction

from apps.notification.models import NotificationChannel


@dataclass
class _BulkFailure:
    id: int
    reason: str


def _bulk_failure_dicts(failures: list[_BulkFailure]) -> list[dict[str, Any]]:
    return [asdict(f) for f in failures]


def bulk_set_channel_state(
    *,
    organization_id: int,
    ids: list[int],
    is_active: bool,
) -> dict[str, Any]:
    """Enable or disable a set of channels in a single transaction.

    Returns ``{"updated": [ids...], "failed": [{"id": int, "reason": str}, ...]}``.
    IDs that are not part of the caller's organisation are reported as
    ``not_found`` rather than leaking the existence of other tenants'
    channels.
    """
    if not ids:
        return {"updated": [], "failed": []}
    # Deduplicate while preserving order; keep the original int type.
    unique_ids: list[int] = []
    seen: set[int] = set()
    for raw in ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)

    existing = list(
        NotificationChannel.objects.filter(
            organization_id=organization_id,
            id__in=unique_ids,
        )
    )
    by_id = {int(ch.id): ch for ch in existing}
    failed: list[_BulkFailure] = [
        _BulkFailure(id=channel_id, reason="not_found")
        for channel_id in unique_ids
        if channel_id not in by_id
    ]
    updated: list[int] = []
    with transaction.atomic():
        for ch in existing:
            if ch.is_active == is_active:
                updated.append(int(ch.id))
                continue
            ch.is_active = is_active
            ch.save(update_fields=["is_active", "updated_at"])
            updated.append(int(ch.id))
    return {"updated": updated, "failed": _bulk_failure_dicts(failed)}


def bulk_delete_channels(
    *,
    organization_id: int,
    ids: list[int],
) -> dict[str, Any]:
    """Delete a set of channels scoped to the caller's organisation."""
    if not ids:
        return {"deleted": [], "failed": []}
    unique_ids: list[int] = []
    seen: set[int] = set()
    for raw in ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)

    existing = list(
        NotificationChannel.objects.filter(
            organization_id=organization_id,
            id__in=unique_ids,
        )
    )
    by_id = {int(ch.id): ch for ch in existing}
    failed: list[_BulkFailure] = [
        _BulkFailure(id=channel_id, reason="not_found")
        for channel_id in unique_ids
        if channel_id not in by_id
    ]
    deleted: list[int] = []
    for ch in existing:
        ch_id = int(ch.id)
        ch.delete()
        deleted.append(ch_id)
    return {"deleted": deleted, "failed": _bulk_failure_dicts(failed)}
