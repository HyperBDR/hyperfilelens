from __future__ import annotations

from django.db import models


class BackupPolicy(models.Model):
    organization_id = models.BigIntegerField(db_index=True)
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True, db_index=True)
    schedule = models.JSONField(default=dict, blank=True)
    retention = models.JSONField(default=dict, blank=True)
    throttling = models.JSONField(default=dict, blank=True)
    error_handling = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "protection_backup_policy"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["organization_id", "is_active", "created_at"],
                name="prot_bpol_org_act_cr_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization_id", "name"],
                name="uniq_prot_bpol_org_name",
            ),
        ]

    def __str__(self) -> str:
        return self.name
