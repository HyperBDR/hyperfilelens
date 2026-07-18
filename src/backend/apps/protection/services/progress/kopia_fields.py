from __future__ import annotations

from typing import Any

from apps.protection.services.progress.bytes_sanity import (
    apply_reference_bytes_total,
    credible_bytes_total,
    monotonic_bytes_total,
)

_ORCHESTRATION_PHASES = frozenset(
    {
        "orchestration",
        "repository_prepare",
        "repository_ready",
        "snapshot_start",
        "started",
    }
)
_ACTIVE_LANE_STATUSES = frozenset({"pending", "dispatching", "running", "creating"})


def progress_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def progress_int(value: Any) -> int:
    parsed = progress_number(value)
    if parsed is None:
        return 0
    return max(0, int(parsed))


def is_orchestration_progress(progress: dict[str, Any] | None) -> bool:
    if not isinstance(progress, dict) or not progress:
        return False
    phase = str(progress.get("phase") or "").strip().lower()
    if phase == "orchestration":
        return True
    kopia_phase = str(progress.get("kopia_phase") or progress.get("orchestration_phase") or "").strip().lower()
    return kopia_phase in _ORCHESTRATION_PHASES


def normalize_lane_progress(
    *,
    progress: dict[str, Any] | None,
    status: str,
    frozen_bytes_done: int = 0,
    frozen_bytes_total: int = 0,
    reference_bytes_total: int = 0,
) -> dict[str, Any]:
    if status in {"success", "available", "completed"} and frozen_bytes_total > 0:
        return _lane_from_bytes(
            kopia_phase="done",
            bytes_done=frozen_bytes_total,
            bytes_total=frozen_bytes_total,
            percent=100.0,
            progress=progress or {},
        )
    if not isinstance(progress, dict) or not progress:
        return _empty_lane(kopia_phase="pending" if status in _ACTIVE_LANE_STATUSES else status)

    if is_orchestration_progress(progress):
        return {
            "kopia_phase": str(progress.get("kopia_phase") or progress.get("orchestration_phase") or "orchestration"),
            "orchestration_label": str(progress.get("orchestration_label") or "").strip(),
            "bytes_done": 0,
            "bytes_total": None,
            "bytes_total_known": False,
            "percent": None,
            "speed_bps": None,
            "eta_seconds": None,
            "kopia_eta_seconds": None,
            "progress_text": str(progress.get("progress_text") or "").strip(),
            "path_index": progress_int(progress.get("path_index")) or None,
            "path_total": progress_int(progress.get("path_total")) or None,
            "percent_source": None,
            "is_transfer": False,
        }

    bytes_done = progress_int(progress.get("bytes_done"))
    bytes_total = progress_int(progress.get("bytes_total"))
    bytes_total_known = bool(progress.get("bytes_total_known")) or bytes_total > 0
    uploaded = progress_int(progress.get("uploaded_bytes"))
    hashed = progress_int(progress.get("hashed_bytes"))
    kopia_phase = str(progress.get("kopia_phase") or "").lower()
    is_restore_lane = (
        kopia_phase == "restoring"
        or "processed_count" in progress
        or "file_done" in progress
    )
    is_backup_lane = not is_restore_lane and (
        "uploaded_count" in progress
        or "hashed_count" in progress
        or str(progress.get("phase") or "").lower() == "kopia_transfer"
    )
    if is_restore_lane:
        processed_bytes = progress_int(progress.get("processed_bytes"))
        bytes_done = processed_bytes or bytes_done
    elif is_backup_lane:
        bytes_done = uploaded
    elif bytes_done <= 0:
        processed = progress_int(progress.get("processed_bytes"))
        bytes_done = uploaded or hashed or processed
    elif uploaded > 0:
        bytes_done = uploaded
    if bytes_total <= 0:
        bytes_total = progress_int(progress.get("estimated_bytes")) or progress_int(progress.get("total_bytes"))
        bytes_total_known = bytes_total > 0
    reference = max(
        0,
        int(reference_bytes_total or 0),
        progress_int(progress.get("reference_bytes_total")),
    )
    bytes_total_reference = False
    if bytes_total_known and bytes_total > 0 and reference > 0:
        bytes_total, bytes_total_reference = apply_reference_bytes_total(
            bytes_total=bytes_total,
            reference_bytes_total=reference,
        )
        if bytes_total is None:
            bytes_total_known = False
        else:
            bytes_total_known = True
    phase = str(progress.get("kopia_phase") or "").lower()
    if not bytes_total_known and bytes_done > 0:
        if phase == "uploading" and hashed > bytes_done:
            bytes_total = hashed
            bytes_total_known = True
        elif (
            phase == "uploading"
            and hashed > 0
            and uploaded >= hashed
            and progress_int(progress.get("estimated_bytes")) <= 0
        ):
            # Upload caught up to hashed batch; more data may still be processed.
            bytes_total = None
            bytes_total_known = False
    elif (
        phase == "uploading"
        and bytes_total_known
        and bytes_total is not None
        and bytes_total > 0
        and bytes_done >= bytes_total
        and progress_int(progress.get("estimated_bytes")) <= 0
        and status in _ACTIVE_LANE_STATUSES
    ):
        bytes_total = None
        bytes_total_known = False
    elif bytes_total_known and bytes_total is not None and not credible_bytes_total(
        bytes_done=bytes_done,
        bytes_total=bytes_total,
    ):
        if reference > 0:
            bytes_total = reference
            bytes_total_reference = True
        else:
            bytes_total = None
            bytes_total_known = False

    prev_max = progress_int((progress or {}).get("_max_bytes_total"))
    if bytes_total_known and bytes_total > 0:
        monotonic = monotonic_bytes_total(
            bytes_done=bytes_done,
            bytes_total=bytes_total,
            previous_max=prev_max or None,
            reference_bytes_total=reference or None,
        )
        if monotonic is None:
            bytes_total = None
            bytes_total_known = False
        else:
            bytes_total = monotonic
    elif bytes_done > 0 and prev_max > 0:
        monotonic = monotonic_bytes_total(
            bytes_done=bytes_done,
            bytes_total=None,
            previous_max=prev_max,
            reference_bytes_total=reference or None,
        )
        if monotonic is not None and credible_bytes_total(bytes_done=bytes_done, bytes_total=monotonic):
            bytes_total = monotonic
            bytes_total_known = True
            bytes_total_reference = reference > 0 and monotonic == reference
    elif reference > 0 and bytes_done > 0 and not bytes_total_known:
        bytes_total = reference
        bytes_total_known = True
        bytes_total_reference = True

    percent: float | None
    percent_source: str | None
    if bytes_total_known and bytes_total is not None and bytes_total > 0:
        percent = min(100.0, max(0.0, 100.0 * bytes_done / bytes_total))
        percent_source = "computed"
    else:
        percent = progress_number(progress.get("kopia_percent"))
        if percent is None:
            percent = progress_number(progress.get("percent"))
        percent_source = "kopia" if percent is not None else None

    if status in _ACTIVE_LANE_STATUSES and percent is not None and percent >= 100:
        percent = 99.0

    hash_speed_bps = progress_int(progress.get("hash_speed_bps")) or None
    upload_speed_bps = progress_int(progress.get("upload_speed_bps")) or None
    speed_bps = upload_speed_bps or progress_int(progress.get("speed_bps")) or None
    kopia_eta = progress_int(progress.get("kopia_eta_seconds")) or None

    return _lane_from_bytes(
        kopia_phase=str(progress.get("kopia_phase") or progress.get("phase") or "running"),
        bytes_done=bytes_done,
        bytes_total=bytes_total if bytes_total_known else None,
        percent=percent,
        progress=progress,
        speed_bps=speed_bps,
        hash_speed_bps=hash_speed_bps,
        upload_speed_bps=upload_speed_bps,
        kopia_eta_seconds=kopia_eta or None,
        percent_source=percent_source,
        bytes_total_reference=bytes_total_reference,
    )


def _lane_from_bytes(
    *,
    kopia_phase: str,
    bytes_done: int,
    bytes_total: int | None,
    percent: float | None,
    progress: dict[str, Any],
    speed_bps: int | None = None,
    hash_speed_bps: int | None = None,
    upload_speed_bps: int | None = None,
    kopia_eta_seconds: int | None = None,
    percent_source: str | None = None,
    bytes_total_reference: bool = False,
) -> dict[str, Any]:
    bytes_total_known = bytes_total is not None and bytes_total > 0
    return {
        "kopia_phase": kopia_phase,
        "orchestration_label": "",
        "bytes_done": bytes_done,
        "bytes_total": bytes_total,
        "bytes_total_known": bytes_total_known,
        "bytes_total_reference": bytes_total_reference,
        "uploaded_bytes": progress_int(progress.get("uploaded_bytes")),
        "hashed_bytes": progress_int(progress.get("hashed_bytes")),
        "uploaded_count": progress_int(progress.get("uploaded_count")),
        "hashed_count": progress_int(progress.get("hashed_count")),
        "estimated_bytes": progress_int(progress.get("estimated_bytes")),
        "processed_count": progress_int(progress.get("processed_count")) or progress_int(progress.get("file_done")),
        "total_count": progress_int(progress.get("total_count")) or progress_int(progress.get("file_total")),
        "percent": percent,
        "speed_bps": speed_bps,
        "hash_speed_bps": hash_speed_bps,
        "upload_speed_bps": upload_speed_bps,
        "eta_seconds": kopia_eta_seconds,
        "kopia_eta_seconds": kopia_eta_seconds,
        "progress_text": str(progress.get("progress_text") or "").strip(),
        "path_index": progress_int(progress.get("path_index")) or None,
        "path_total": progress_int(progress.get("path_total")) or None,
        "percent_source": percent_source,
        "is_transfer": True,
    }


def _empty_lane(*, kopia_phase: str) -> dict[str, Any]:
    return {
        "kopia_phase": kopia_phase,
        "orchestration_label": "",
        "bytes_done": 0,
        "bytes_total": None,
        "bytes_total_known": False,
        "percent": None,
        "speed_bps": None,
        "eta_seconds": None,
        "kopia_eta_seconds": None,
        "progress_text": "",
        "path_index": None,
        "path_total": None,
        "percent_source": None,
        "is_transfer": False,
    }
