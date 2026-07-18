from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone

_MIN_SPEED_BPS = 100
_MIN_SAMPLE_GAP_SECONDS = 2.0
_KOPIA_ETA_MIN_REMAINING_RATIO = 0.1
_KOPIA_ETA_MAX_COMPUTED_RATIO = 3.0


def _computed_eta_seconds(*, bytes_done: int, bytes_total: int, speed_bps: int) -> int | None:
    remaining = int(bytes_total) - int(bytes_done)
    if remaining <= 0 or speed_bps <= 0:
        return None
    return int(remaining / speed_bps)


def _kopia_eta_credible(*, kopia_eta: int, remaining: int, speed_bps: int) -> bool:
    if kopia_eta <= 0 or remaining <= 0 or speed_bps <= 0:
        return False
    implied_bytes = kopia_eta * speed_bps
    if implied_bytes < remaining * _KOPIA_ETA_MIN_REMAINING_RATIO:
        return False
    computed = remaining / speed_bps
    if kopia_eta > computed * _KOPIA_ETA_MAX_COMPUTED_RATIO:
        return False
    return True


def _lane_speed_counter(lane: dict[str, Any]) -> int:
    phase = str(lane.get("kopia_phase") or "").lower()
    uploaded = int(lane.get("uploaded_bytes") or 0)
    hashed = int(lane.get("hashed_bytes") or 0)
    bytes_done = int(lane.get("bytes_done") or 0)
    if phase == "uploading" and uploaded > 0:
        return uploaded
    if phase == "hashing" and hashed > 0:
        return hashed
    return bytes_done


def apply_speed_and_eta(
    *,
    lane: dict[str, Any],
    sample: dict[str, Any] | None,
    now: datetime | None = None,
    persist_sample: bool = True,
) -> dict[str, Any]:
    now = now or timezone.now()
    result = dict(lane)
    counter = _lane_speed_counter(result)
    bytes_done = int(result.get("bytes_done") or 0)
    bytes_total = result.get("bytes_total")
    bytes_total_known = bool(result.get("bytes_total_known"))

    speed_bps = result.get("speed_bps")
    hash_speed_bps = result.get("hash_speed_bps")
    upload_speed_bps = result.get("upload_speed_bps")
    speed_source = result.get("speed_source") or ("kopia" if speed_bps else None)
    hash_speed_source = result.get("hash_speed_source") or ("kopia" if hash_speed_bps else None)
    upload_speed_source = result.get("upload_speed_source") or ("kopia" if upload_speed_bps else None)
    prev = sample if isinstance(sample, dict) else {}
    prev_counter = int(prev.get("counter") or prev.get("bytes_done") or 0)
    phase = str(result.get("kopia_phase") or "").lower()

    if not hash_speed_bps and not upload_speed_bps and isinstance(sample, dict):
        prev_at_raw = prev.get("sampled_at")
        if prev_at_raw and counter > prev_counter:
            try:
                prev_at = datetime.fromisoformat(str(prev_at_raw).replace("Z", "+00:00"))
                delta_t = (now - prev_at).total_seconds()
                if delta_t >= _MIN_SAMPLE_GAP_SECONDS:
                    computed = int((counter - prev_counter) / delta_t)
                    if computed >= _MIN_SPEED_BPS:
                        if phase == "uploading":
                            upload_speed_bps = computed
                            upload_speed_source = "delta"
                        else:
                            hash_speed_bps = computed
                            hash_speed_source = "delta"
            except (TypeError, ValueError, OverflowError):
                pass

    if hash_speed_bps:
        result["hash_speed_bps"] = int(hash_speed_bps)
        result["hash_speed_source"] = hash_speed_source
    else:
        result["hash_speed_bps"] = None
        result["hash_speed_source"] = None

    if upload_speed_bps:
        result["upload_speed_bps"] = int(upload_speed_bps)
        result["upload_speed_source"] = upload_speed_source
    else:
        result["upload_speed_bps"] = None
        result["upload_speed_source"] = None

    speed_bps = upload_speed_bps or hash_speed_bps or speed_bps
    if speed_bps:
        result["speed_bps"] = int(speed_bps)
        result["speed_source"] = upload_speed_source or hash_speed_source or speed_source
    else:
        result["speed_bps"] = None
        result["speed_source"] = None

    kopia_eta = result.get("kopia_eta_seconds") or result.get("eta_seconds")
    computed_eta: int | None = None
    remaining = 0
    if bytes_total_known and bytes_total is not None and speed_bps:
        remaining = int(bytes_total) - bytes_done
        computed_eta = _computed_eta_seconds(
            bytes_done=bytes_done,
            bytes_total=int(bytes_total),
            speed_bps=int(speed_bps),
        )

    eta_seconds = None
    eta_source = None
    if bytes_total_known and computed_eta is not None:
        if kopia_eta and _kopia_eta_credible(
            kopia_eta=int(kopia_eta),
            remaining=remaining,
            speed_bps=int(speed_bps),
        ):
            eta_seconds = int(kopia_eta)
            eta_source = "kopia"
        else:
            eta_seconds = computed_eta
            eta_source = "computed"
    elif kopia_eta:
        eta_seconds = int(kopia_eta)
        eta_source = "kopia"
    elif computed_eta is not None:
        eta_seconds = computed_eta
        eta_source = "computed"

    result["eta_seconds"] = eta_seconds
    result["eta_source"] = eta_source

    max_total = int(result.get("bytes_total") or 0) if bytes_total_known else int(prev.get("_max_bytes_total") or 0)
    if bytes_total_known and bytes_total is not None:
        max_total = max(max_total, int(bytes_total))

    if persist_sample and counter > prev_counter:
        result["last_sample"] = {
            "bytes_done": bytes_done,
            "counter": counter,
            "sampled_at": now.isoformat(),
            "_max_bytes_total": max_total,
        }
    elif isinstance(sample, dict) and sample:
        result["last_sample"] = dict(sample)
    else:
        result["last_sample"] = {
            "bytes_done": bytes_done,
            "counter": counter,
            "sampled_at": now.isoformat(),
            "_max_bytes_total": max_total,
        }
    return result
