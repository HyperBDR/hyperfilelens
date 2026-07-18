"""Notification delivery log (alert and platform events)."""

import uuid

from django.db import models

from apps.iam.models import Organization

from apps.notification.constants import NotificationLogStatus, NotificationLogType


class NotificationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    channel = models.ForeignKey(
        "notification.NotificationChannel",
        on_delete=models.CASCADE,
        related_name="logs",
    )
    alert_record_id = models.UUIDField(null=True, blank=True, db_index=True)
    event_type = models.CharField(max_length=120, blank=True, default="", db_index=True)
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationLogType.choices,
        default=NotificationLogType.FIRING,
    )
    status = models.CharField(max_length=50, choices=NotificationLogStatus.choices)
    error_message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notification_logs"
        ordering = ["-sent_at", "-id"]
        indexes = [
            models.Index(
                fields=["organization", "status", "sent_at"],
                name="notif_log_org_st_sent_idx",
            ),
        ]
