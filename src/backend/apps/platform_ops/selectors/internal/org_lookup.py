"""Organization lookup helpers for platform ops (Task uses organization_id)."""

from __future__ import annotations

from collections.abc import Iterable

from apps.iam.models import Organization


def organization_map(org_ids: Iterable[int]) -> dict[int, dict[str, str]]:
    ids = {int(x) for x in org_ids if x}
    if not ids:
        return {}
    rows = Organization.objects.filter(id__in=ids).values("id", "key", "name")
    return {row["id"]: {"key": row["key"], "name": row["name"]} for row in rows}


def organization_ids_for_key(org_key: str) -> list[int]:
    key = (org_key or "").strip()
    if not key:
        return []
    return list(Organization.objects.filter(key=key).values_list("id", flat=True))


def organization_ids_matching(term: str) -> list[int]:
    term = (term or "").strip()
    if not term:
        return []
    from django.db.models import Q

    return list(
        Organization.objects.filter(Q(key__icontains=term) | Q(name__icontains=term)).values_list(
            "id",
            flat=True,
        )
    )
