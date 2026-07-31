"""Shared durable lease policy for Lens lifecycle workers."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

TEARDOWN_TASK_HARD_LIMIT_SECONDS = int(
    getattr(settings, "LENS_KS_SYNC_TIME_LIMIT", 7200)
)
TEARDOWN_CLAIM_TTL_SECONDS = TEARDOWN_TASK_HARD_LIMIT_SECONDS + 300
PROVISION_TASK_HARD_LIMIT_SECONDS = TEARDOWN_TASK_HARD_LIMIT_SECONDS
PROVISION_CLAIM_TTL_SECONDS = PROVISION_TASK_HARD_LIMIT_SECONDS + 300


def next_retry_at(attempts: int) -> datetime:
    """Return bounded exponential retry time for a teardown attempt."""

    delay_seconds = min(3600, 60 * (2 ** min(max(attempts - 1, 0), 6)))
    return timezone.now() + timedelta(seconds=delay_seconds)
