from django.db import models

from apps.iam.models import Organization
from apps.protection.models import BackupSourceSnapshotDirectory


class InsightReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="insight_reports",
    )
    snapshot = models.ForeignKey(
        BackupSourceSnapshotDirectory,
        on_delete=models.CASCADE,
        related_name="insight_reports",
    )
    report_type = models.CharField(max_length=50, db_index=True, default="ai_scan")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    summary = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "insight_report"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["organization", "report_type", "created_at"]),
        ]


class InsightFinding(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="insight_findings",
    )
    snapshot = models.ForeignKey(
        BackupSourceSnapshotDirectory,
        on_delete=models.CASCADE,
        related_name="insight_findings",
    )
    report = models.ForeignKey(
        InsightReport,
        on_delete=models.CASCADE,
        related_name="findings",
    )
    finding_type = models.CharField(max_length=80, db_index=True)
    severity = models.CharField(max_length=20, default="info", db_index=True)
    title = models.CharField(max_length=300)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "insight_finding"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["organization", "snapshot", "created_at"]),
            models.Index(fields=["organization", "finding_type", "created_at"]),
        ]
