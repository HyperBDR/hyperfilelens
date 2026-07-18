from django.db import models

from apps.iam.models import Organization

from apps.notification.constants import ChannelType


class NotificationChannel(models.Model):
    Type = ChannelType

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="notification_channels",
    )
    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=50, choices=Type.choices, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_channels"
        ordering = ["organization_id", "name", "id"]


class NotificationDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event_type = models.CharField(max_length=120, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    error = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notification_deliveries"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
        ]

