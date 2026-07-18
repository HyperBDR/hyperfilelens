from __future__ import annotations

from typing import Any

from apps.protection.services.progress.creep import progress_creep

_ACTIVE_LANE_STATUSES = frozenset({"pending", "dispatching", "running", "creating"})

_PLACEHOLDER_PERCENT = {
    "preparing": 3.0,
    "dispatching": 3.0,
    "estimating": 8.0,
    "finalizing": 95.0,
}

_TRANSFER_UNKNOWN_START = 3.0
_TRANSFER_UNKNOWN_END = 15.0


def has_transfer_progress(lanes: list[dict[str, Any]]) -> bool:
    for lane in lanes:
        progress = lane.get("progress") or {}
        if not isinstance(progress, dict) or not progress.get("is_transfer"):
            continue
        if progress.get("bytes_total_known"):
            return True
        if int(progress.get("bytes_done") or 0) > 0:
            return True
        if progress.get("percent") not in (None, ""):
            return True
    return False


def enrich_kopia_progress_payload(
    payload: dict[str, Any],
    *,
    transfer_progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phase = str(payload.get("orchestration_phase") or "").strip().lower()
    aggregate = payload.get("aggregate") if isinstance(payload.get("aggregate"), dict) else {}
    transfer = transfer_progress if isinstance(transfer_progress, dict) else {}

    if phase == "done":
        payload["display_percent"] = 100.0
        payload["percent_source"] = "kopia"
        payload["show_metrics"] = True
        return payload

    if phase == "failed":
        percent = aggregate.get("percent")
        payload["display_percent"] = float(percent) if percent is not None else 0.0
        payload["percent_source"] = "kopia"
        payload["show_metrics"] = bool(aggregate.get("bytes_total_known") or aggregate.get("bytes_done"))
        return payload

    if phase == "transferring":
        if not aggregate.get("bytes_total_known"):
            payload["display_percent"] = progress_creep(
                started_at_raw=transfer.get("unknown_total_started_at"),
                start_percent=_TRANSFER_UNKNOWN_START,
                end_percent=_TRANSFER_UNKNOWN_END,
            )
            payload["percent_source"] = "placeholder"
            payload["show_metrics"] = False
            return payload

        percent = aggregate.get("percent")
        payload["display_percent"] = float(percent) if percent is not None else 0.0
        payload["percent_source"] = "kopia"
        payload["show_metrics"] = bool(
            (aggregate.get("bytes_done") or 0) > 0
            or aggregate.get("speed_bps")
            or aggregate.get("hash_speed_bps")
            or aggregate.get("upload_speed_bps")
            or aggregate.get("bytes_total_known")
        )
        return payload

    placeholder = _PLACEHOLDER_PERCENT.get(phase)
    if placeholder is not None:
        payload["display_percent"] = placeholder
        payload["percent_source"] = "placeholder"
        payload["show_metrics"] = bool(
            aggregate.get("bytes_total_known")
            and aggregate.get("bytes_total_reference")
        )
        return payload

    payload["display_percent"] = 3.0
    payload["percent_source"] = "placeholder"
    payload["show_metrics"] = False
    return payload
