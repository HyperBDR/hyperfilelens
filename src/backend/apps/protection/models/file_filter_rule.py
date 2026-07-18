from __future__ import annotations

from django.db import models


class FileFilterRule(models.Model):
    organization_id = models.BigIntegerField(db_index=True)
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True, db_index=True)
    ignore_patterns = models.TextField(blank=True, default="")
    large_file_limit_enabled = models.BooleanField(default=False)
    large_file_bytes_max = models.BigIntegerField(default=0)
    ignore_cache_directories = models.BooleanField(default=True)
    current_filesystem_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "protection_file_filter_rule"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["organization_id", "is_active", "created_at"],
                name="prot_ffr_org_act_cr_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization_id", "name"],
                name="uniq_prot_ffr_org_name",
            ),
        ]

    def __str__(self) -> str:
        return self.name
