"""Backward-compatible re-export; prefer services.interface."""

from apps.notification.services.internal.dispatcher import (
    DeliveryAttemptResult,
    attempt_delivery,
)

__all__ = ["attempt_delivery", "DeliveryAttemptResult"]
