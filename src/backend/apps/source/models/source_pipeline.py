"""Backup wizard pipeline step for real selectable sources (agent / NAS)."""

from django.db import models
from django.utils import timezone

from apps.node.models.base import OrganizationScopedModel
from apps.source.constants import PipelineStep, PipelineTaskStatus, SelectableSourceKind


class SourceBackupPipelineEntry(OrganizationScopedModel):
    """Application-maintained read model for a real backup-selectable source."""

    organization = models.ForeignKey(
        "iam.Organization",
        on_delete=models.CASCADE,
        related_name="source_backup_pipeline_entries",
    )
    source_kind = models.CharField(max_length=16, choices=SelectableSourceKind.CHOICES)
    ref_id = models.BigIntegerField()
    step = models.PositiveSmallIntegerField(choices=PipelineStep.CHOICES, default=PipelineStep.SOURCE_POOL)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    source_name = models.CharField(max_length=255, blank=True, default="")
    source_hostname = models.CharField(max_length=255, blank=True, default="")
    source_ip = models.CharField(max_length=64, blank=True, default="")
    source_status = models.CharField(max_length=32, blank=True, default="")
    source_availability = models.CharField(max_length=20, choices=(("online", "Online"), ("offline", "Offline")), default="offline")
    last_backup_status = models.CharField(max_length=20, choices=PipelineTaskStatus.CHOICES, default=PipelineTaskStatus.NONE)
    last_restore_status = models.CharField(max_length=20, choices=PipelineTaskStatus.CHOICES, default=PipelineTaskStatus.NONE)
    last_backup_task_id = models.BigIntegerField(null=True, blank=True)
    last_restore_task_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "source_backup_pipeline"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_kind", "ref_id"],
                name="uniq_source_backup_pipeline_org_kind_ref",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "step", "-created_at", "-id"],
                condition=models.Q(is_deleted=False),
                name="src_pipe_org_step_ord_idx",
            ),
            models.Index(
                fields=["organization", "source_status", "-created_at", "-id"],
                condition=models.Q(is_deleted=False),
                name="src_pipe_org_status_idx",
            ),
            models.Index(fields=["organization", "source_availability", "-created_at", "-id"], condition=models.Q(is_deleted=False), name="src_pipe_org_avail_idx"),
            models.Index(fields=["organization", "last_backup_status", "-created_at", "-id"], condition=models.Q(is_deleted=False), name="src_pipe_org_bkstat_idx"),
            models.Index(fields=["organization", "last_restore_status", "-created_at", "-id"], condition=models.Q(is_deleted=False), name="src_pipe_org_rststat_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.source_kind}:{self.ref_id} step={self.step}"
