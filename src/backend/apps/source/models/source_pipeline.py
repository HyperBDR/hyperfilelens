"""Backup wizard pipeline step for real selectable sources (agent / NAS)."""

from django.db import models

from apps.node.models.base import OrganizationScopedModel
from apps.source.constants import PipelineStep, SelectableSourceKind


class SourceBackupPipelineEntry(OrganizationScopedModel):
    """Tracks protection flow step (1/2/3) for real backup-selectable sources.

    Demo sources (h1, nas1, …) stay in the frontend demo store only.
    Absence of a row means pipeline step 1 (backup source pool).
    """

    organization = models.ForeignKey(
        "iam.Organization",
        on_delete=models.CASCADE,
        related_name="source_backup_pipeline_entries",
    )
    source_kind = models.CharField(max_length=16, choices=SelectableSourceKind.CHOICES)
    ref_id = models.BigIntegerField()
    step = models.PositiveSmallIntegerField(choices=PipelineStep.CHOICES, default=PipelineStep.SOURCE_POOL)

    class Meta:
        db_table = "source_backup_pipeline"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_kind", "ref_id"],
                name="uniq_source_backup_pipeline_org_kind_ref",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "step"],
                name="source_back_organiz_0f0f0f_idx",
            ),
            models.Index(
                fields=["organization", "source_kind", "ref_id"],
                name="source_back_organiz_1a1a1a_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_kind}:{self.ref_id} step={self.step}"
