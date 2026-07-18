"""Public notification service API — sole write entry for outbound delivery."""

from apps.notification.services.internal.channel_test import test_channel
from apps.notification.services.internal.dispatcher import (
    DeliveryAttemptResult,
    attempt_delivery,
)

__all__ = ["attempt_delivery", "DeliveryAttemptResult", "test_channel"]
