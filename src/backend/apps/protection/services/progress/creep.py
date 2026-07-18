from __future__ import annotations

from datetime import datetime

from django.utils import timezone

CREEP_STEP_SECONDS = 30.0
CREEP_STEP_PERCENT = 0.2


def progress_creep(
    *,
    started_at_raw: str | None,
    start_percent: float,
    end_percent: float,
    now: datetime | None = None,
) -> float:
    now = now or timezone.now()
    if not started_at_raw:
        return start_percent
    try:
        started_at = datetime.fromisoformat(str(started_at_raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return start_percent
    elapsed = max(0.0, (now - started_at).total_seconds())
    steps = min(
        (end_percent - start_percent) / CREEP_STEP_PERCENT,
        elapsed / CREEP_STEP_SECONDS,
    )
    return min(end_percent, start_percent + steps * CREEP_STEP_PERCENT)
