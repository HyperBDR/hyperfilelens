"""Platform-wide runtime settings stored in DB (overlay over .env defaults)."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class PlatformRuntimeSetting(models.Model):
    key = models.CharField(max_length=128, unique=True, db_index=True)
    value_text = models.TextField(blank=True, default="")
    secret_ciphertext = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_runtime_settings_updated",
    )

    class Meta:
        db_table = "platform_runtime_settings"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key
