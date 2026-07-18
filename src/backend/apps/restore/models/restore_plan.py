from __future__ import annotations

from django.db import models


class RestorePlan(models.Model):
    class EndpointType(models.TextChoices):
        AGENT = "agent", "Agent"
        NAS = "nas", "NAS"

    class ConflictMode(models.TextChoices):
        SKIP = "skip", "Skip"
        OVERWRITE = "overwrite", "Overwrite"

    class Scope(models.TextChoices):
        SNAPSHOT = "snapshot", "Snapshot"
        PATHS = "paths", "Paths"

    organization_id = models.BigIntegerField(db_index=True)
    backup_config_id = models.BigIntegerField(db_index=True)
    backup_config_dir_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    scope = models.CharField(max_length=16, choices=Scope.choices, default=Scope.PATHS)
    source_type = models.CharField(max_length=16, choices=EndpointType.choices)
    source_ref_id = models.BigIntegerField()
    source_path = models.CharField(max_length=1000, blank=True, default="")
    target_type = models.CharField(max_length=16, choices=EndpointType.choices)
    target_ref_id = models.BigIntegerField()
    restore_dir = models.CharField(max_length=1000)
    conflict_mode = models.CharField(max_length=16, choices=ConflictMode.choices)
    enabled = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restore_plan"
        ordering = ["source_type", "source_ref_id", "sort_order", "id"]
        indexes = [
            models.Index(
                fields=["organization_id", "source_type", "source_ref_id"],
                name="restore_plan_org_src_idx",
            ),
            models.Index(
                fields=["organization_id", "target_type", "target_ref_id"],
                name="restore_plan_org_tgt_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_type}/{self.source_ref_id}:{self.source_path}"
