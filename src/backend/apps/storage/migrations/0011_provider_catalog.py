import uuid

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0010_repository_task_control"),
        ("task", "0009_storage_provider_validation_task"),
    ]

    operations = [
        migrations.AlterField(
            model_name="repository",
            name="s3_platform",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.CreateModel(
            name="StorageProviderOverride",
            fields=[
                (
                    "provider_id",
                    models.CharField(max_length=50, primary_key=True, serialize=False),
                ),
                ("schema_version", models.PositiveSmallIntegerField()),
                ("config", models.JSONField()),
                ("checksum", models.CharField(max_length=64)),
                ("updated_by_id", models.BigIntegerField(blank=True, null=True)),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        db_default=django.db.models.functions.datetime.Now(),
                    ),
                ),
            ],
            options={
                "db_table": "storage_provider_override",
                "ordering": ["provider_id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(schema_version__gte=1),
                        name="stor_prov_schema_gte_1",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            provider_id__regex="^[a-z][a-z0-9_-]{0,49}$"
                        ),
                        name="stor_prov_id_format",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(checksum__regex="^[0-9a-f]{64}$"),
                        name="stor_prov_checksum_format",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE storage_provider_override "
                "ADD CONSTRAINT stor_prov_config_object "
                "CHECK (jsonb_typeof(config) = 'object')"
            ),
            reverse_sql=(
                "ALTER TABLE storage_provider_override "
                "DROP CONSTRAINT stor_prov_config_object"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE storage_provider_override "
                "ADD CONSTRAINT stor_prov_config_id "
                "CHECK (config ? 'id' AND config->>'id' = provider_id)"
            ),
            reverse_sql=(
                "ALTER TABLE storage_provider_override "
                "DROP CONSTRAINT stor_prov_config_id"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE storage_provider_override "
                "ADD CONSTRAINT stor_prov_config_name "
                "CHECK (config ? 'display_name' "
                "AND jsonb_typeof(config->'display_name') = 'string' "
                "AND length(btrim(config->>'display_name')) BETWEEN 1 AND 200)"
            ),
            reverse_sql=(
                "ALTER TABLE storage_provider_override "
                "DROP CONSTRAINT stor_prov_config_name"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE storage_provider_override "
                "ADD CONSTRAINT stor_prov_config_enabled "
                "CHECK (config ? 'enabled' "
                "AND jsonb_typeof(config->'enabled') = 'boolean')"
            ),
            reverse_sql=(
                "ALTER TABLE storage_provider_override "
                "DROP CONSTRAINT stor_prov_config_enabled"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE storage_provider_override "
                "ADD CONSTRAINT stor_prov_config_regions "
                "CHECK (config ? 'regions' "
                "AND jsonb_typeof(config->'regions') = 'array')"
            ),
            reverse_sql=(
                "ALTER TABLE storage_provider_override "
                "DROP CONSTRAINT stor_prov_config_regions"
            ),
        ),
        migrations.CreateModel(
            name="StorageProviderValidationRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("task_id", models.BigIntegerField(unique=True)),
                ("provider_id", models.CharField(max_length=50, unique=True)),
                ("schema_version", models.PositiveSmallIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("validating", "Validating"),
                            ("cancelling", "Cancelling"),
                            ("validation_failed", "Validation failed"),
                            ("cleanup_required", "Cleanup required"),
                            ("passed", "Passed"),
                            ("cancelled", "Cancelled"),
                            ("expired", "Expired"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("candidate_config", models.JSONField(blank=True, null=True)),
                (
                    "candidate_checksum",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                ("error_code", models.CharField(blank=True, max_length=64, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("requested_by_id", models.BigIntegerField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "storage_provider_validation_run",
                "ordering": ["provider_id"],
                "constraints": [
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
                        condition=models.Q(candidate_checksum__isnull=True)
                        | models.Q(candidate_checksum__regex="^[0-9a-f]{64}$"),
                        name="stor_val_run_candidate_checksum",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(expires_at__gt=models.F("created_at")),
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
                ],
            },
        ),
        migrations.CreateModel(
            name="StorageProviderRegionValidation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("region_id", models.CharField(max_length=100)),
                ("region_group", models.CharField(max_length=100)),
                ("region_group_en", models.CharField(max_length=200)),
                ("external_endpoint", models.CharField(max_length=500)),
                ("internal_endpoint", models.CharField(max_length=500)),
                ("driver", models.CharField(default="s3", max_length=32)),
                (
                    "s3_url_style",
                    models.CharField(default="virtual_hosted", max_length=32),
                ),
                ("use_tls", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("cleanup_failed", "Cleanup failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                (
                    "current_step",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("create_bucket", "Create bucket"),
                            ("initialize_kopia", "Initialize Kopia"),
                            ("backup", "Backup"),
                            ("restore", "Restore"),
                            ("verify_hash", "Verify hash"),
                            ("cleanup_repository", "Cleanup repository"),
                            ("delete_bucket", "Delete bucket"),
                            ("verify_cleanup", "Verify cleanup"),
                        ],
                        max_length=32,
                        null=True,
                    ),
                ),
                ("bucket_name", models.CharField(blank=True, max_length=63, null=True)),
                ("error_code", models.CharField(blank=True, max_length=64, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="region_validations",
                        to="storage.storageprovidervalidationrun",
                    ),
                ),
            ],
            options={
                "db_table": "storage_provider_region_validation",
                "ordering": ["region_id", "id"],
                "indexes": [
                    models.Index(
                        fields=["run", "status"], name="stor_val_run_status_idx"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("run", "region_id"),
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
                        condition=models.Q(current_step__isnull=True)
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
                        ),
                        name="stor_val_region_step_valid",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE storage_provider_validation_run "
                "ADD CONSTRAINT stor_val_run_candidate_object "
                "CHECK (candidate_config IS NULL OR "
                "jsonb_typeof(candidate_config) = 'object')"
            ),
            reverse_sql=(
                "ALTER TABLE storage_provider_validation_run "
                "DROP CONSTRAINT stor_val_run_candidate_object"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE storage_provider_validation_run "
                "ADD CONSTRAINT stor_val_run_provider_id "
                "CHECK (candidate_config IS NULL OR candidate_config->>'id' = provider_id)"
            ),
            reverse_sql=(
                "ALTER TABLE storage_provider_validation_run "
                "DROP CONSTRAINT stor_val_run_provider_id"
            ),
        ),
    ]
