"""Platform-level audit trail for Admin Console staff actions."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class PlatformAuditLog(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_audit_logs",
    )
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=80, db_index=True)
    target_id = models.CharField(max_length=120, blank=True, default="")
    org_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    result = models.CharField(
        max_length=20,
        choices=Result.choices,
        default=Result.SUCCESS,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "platform_ops_audit_log"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"
