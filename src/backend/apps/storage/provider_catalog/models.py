"""Current Provider Catalog override and validation state models."""

from __future__ import annotations

from django.db import models
from django.db.models import F
from django.db.models.functions import Now

import uuid


class StorageProviderOverride(models.Model):
    provider_id = models.CharField(max_length=50, primary_key=True)
    schema_version = models.PositiveSmallIntegerField()
    config = models.JSONField()
    checksum = models.CharField(max_length=64)
    updated_by_id = models.BigIntegerField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "storage_provider_override"
        ordering = ["provider_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(schema_version__gte=1),
                name="stor_prov_schema_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(provider_id__regex=r"^[a-z][a-z0-9_-]{0,49}$"),
                name="stor_prov_id_format",
            ),
            models.CheckConstraint(
                condition=models.Q(checksum__regex=r"^[0-9a-f]{64}$"),
                name="stor_prov_checksum_format",
            ),
        ]

    def __str__(self) -> str:
        return self.provider_id


class StorageProviderValidationRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VALIDATING = "validating", "Validating"
        CANCELLING = "cancelling", "Cancelling"
        VALIDATION_FAILED = "validation_failed", "Validation failed"
        CLEANUP_REQUIRED = "cleanup_required", "Cleanup required"
        PASSED = "passed", "Passed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_id = models.BigIntegerField(unique=True)
    provider_id = models.CharField(max_length=50, unique=True)
    schema_version = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    candidate_config = models.JSONField(blank=True, null=True)
    candidate_checksum = models.CharField(max_length=64, blank=True, null=True)
    error_code = models.CharField(max_length=64, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    requested_by_id = models.BigIntegerField(blank=True, null=True)
    expires_at = models.DateTimeField()
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "storage_provider_validation_run"
        ordering = ["provider_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(schema_version__gte=1),
                name="stor_val_run_schema_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "validating",
                        "cancelling",
                        "validation_failed",
                        "cleanup_required",
                        "passed",
                        "cancelled",
                        "expired",
                    ]
                ),
                name="stor_val_run_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(candidate_checksum__isnull=True)
                    | models.Q(candidate_checksum__regex=r"^[0-9a-f]{64}$")
                ),
                name="stor_val_run_candidate_checksum",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=F("created_at")),
                name="stor_val_run_expiry_after_create",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(status__in=["cancelled", "expired"])
                        & models.Q(candidate_config__isnull=True)
                        & models.Q(candidate_checksum__isnull=True)
                    )
                    | (
                        models.Q(candidate_config__isnull=False)
                        & models.Q(candidate_checksum__isnull=False)
                        & models.Q(requested_by_id__isnull=False)
                    )
                ),
                name="stor_val_run_candidate_fields",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider_id}:{self.id}"


class StorageProviderRegionValidation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CLEANUP_FAILED = "cleanup_failed", "Cleanup failed"
        CANCELLED = "cancelled", "Cancelled"

    class Step(models.TextChoices):
        CREATE_BUCKET = "create_bucket", "Create bucket"
        INITIALIZE_KOPIA = "initialize_kopia", "Initialize Kopia"
        BACKUP = "backup", "Backup"
        RESTORE = "restore", "Restore"
        VERIFY_HASH = "verify_hash", "Verify hash"
        CLEANUP_REPOSITORY = "cleanup_repository", "Cleanup repository"
        DELETE_BUCKET = "delete_bucket", "Delete bucket"
        VERIFY_CLEANUP = "verify_cleanup", "Verify cleanup"

    run = models.ForeignKey(
        StorageProviderValidationRun,
        on_delete=models.CASCADE,
        related_name="region_validations",
    )
    region_id = models.CharField(max_length=100)
    region_group = models.CharField(max_length=100)
    region_group_en = models.CharField(max_length=200)
    external_endpoint = models.CharField(max_length=500)
    internal_endpoint = models.CharField(max_length=500)
    driver = models.CharField(max_length=32, default="s3")
    s3_url_style = models.CharField(max_length=32, default="virtual_hosted")
    use_tls = models.BooleanField(default=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    current_step = models.CharField(
        max_length=32,
        choices=Step.choices,
        blank=True,
        null=True,
    )
    bucket_name = models.CharField(max_length=63, blank=True, null=True)
    error_code = models.CharField(max_length=64, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "storage_provider_region_validation"
        ordering = ["region_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "region_id"],
                name="uniq_stor_val_run_region",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "running",
                        "success",
                        "failed",
                        "cleanup_failed",
                        "cancelled",
                    ]
                ),
                name="stor_val_region_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(current_step__isnull=True)
                    | models.Q(
                        current_step__in=[
                            "create_bucket",
                            "initialize_kopia",
                            "backup",
                            "restore",
                            "verify_hash",
                            "cleanup_repository",
                            "delete_bucket",
                            "verify_cleanup",
                        ]
                    )
                ),
                name="stor_val_region_step_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["run", "status"],
                name="stor_val_run_status_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.region_id}"
