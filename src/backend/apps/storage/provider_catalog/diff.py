"""Deterministic structured Provider configuration differences."""

from __future__ import annotations

from typing import Any


def _field_changes(before: dict, after: dict, fields: tuple[str, ...]) -> list[dict]:
    return [
        {"path": field, "before": before.get(field), "after": after.get(field)}
        for field in fields
        if before.get(field) != after.get(field)
    ]


def provider_diff(
    *,
    provider_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> dict[str, Any]:
    if before is None:
        return {
            "provider_id": provider_id,
            "change_type": "added",
            "provider_changes": [],
            "added_regions": after["regions"],
            "removed_regions": [],
            "modified_regions": [],
            "high_risk_changes": [],
        }

    provider_changes = _field_changes(
        before,
        after,
        ("display_name", "enabled"),
    )
    before_regions = {item["id"]: item for item in before["regions"]}
    after_regions = {item["id"]: item for item in after["regions"]}
    added = [
        after_regions[key]
        for key in sorted(after_regions.keys() - before_regions.keys())
    ]
    removed = [
        before_regions[key]
        for key in sorted(before_regions.keys() - after_regions.keys())
    ]
    modified: list[dict[str, Any]] = []
    high_risk: list[dict[str, str]] = []
    for region_id in sorted(before_regions.keys() & after_regions.keys()):
        changes = _field_changes(
            before_regions[region_id],
            after_regions[region_id],
            (
                "display_name",
                "region_group",
                "region_group_en",
                "external_endpoint",
                "internal_endpoint",
                "driver",
                "s3_url_style",
                "use_tls",
            ),
        )
        if changes:
            modified.append({"region_id": region_id, "changes": changes})
        if any(
            change["path"]
            in {
                "external_endpoint",
                "internal_endpoint",
                "driver",
                "s3_url_style",
                "use_tls",
            }
            for change in changes
        ):
            high_risk.append(
                {
                    "id": f"connection-change:{provider_id}:{region_id}",
                    "type": "connection_change",
                    "path": f"regions.{region_id}",
                }
            )
    for region in removed:
        high_risk.append(
            {
                "id": f"region-delete:{provider_id}:{region['id']}",
                "type": "region_delete",
                "path": f"regions.{region['id']}",
            }
        )
    changed = bool(provider_changes or added or removed or modified)
    return {
        "provider_id": provider_id,
        "change_type": "modified" if changed else "unchanged",
        "provider_changes": provider_changes,
        "added_regions": added,
        "removed_regions": removed,
        "modified_regions": modified,
        "high_risk_changes": high_risk,
    }
