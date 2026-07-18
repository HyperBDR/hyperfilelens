"""Outbound notification channel contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from apps.notification.models import NotificationChannel, NotificationDelivery


class BaseChannel(ABC):
    """Adapter for a single outbound channel implementation."""

    @abstractmethod
    def send(self, *, channel: NotificationChannel, delivery: NotificationDelivery) -> None:
        raise NotImplementedError
