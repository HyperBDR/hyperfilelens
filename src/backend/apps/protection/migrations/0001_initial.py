from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BackupPolicy",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("name", models.CharField(max_length=128)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("schedule", models.JSONField(blank=True, default=dict)),
                ("retention", models.JSONField(blank=True, default=dict)),
                ("throttling", models.JSONField(blank=True, default=dict)),
                ("error_handling", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "protection_backup_policy",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="FileFilterRule",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("name", models.CharField(max_length=128)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("ignore_patterns", models.TextField(blank=True, default="")),
                ("large_file_limit_enabled", models.BooleanField(default=False)),
                ("large_file_bytes_max", models.BigIntegerField(default=0)),
                ("ignore_cache_directories", models.BooleanField(default=True)),
                ("current_filesystem_only", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "protection_file_filter_rule",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="BackupConfig",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("name", models.CharField(max_length=200)),
                ("remark", models.TextField(blank=True, default="")),
                ("source_type", models.CharField(max_length=16)),
                ("source_ref_id", models.BigIntegerField()),
                ("repository_id", models.BigIntegerField(db_index=True)),
                (
                    "backup_policy_id",
                    models.BigIntegerField(blank=True, db_index=True, null=True),
                ),
                (
                    "file_filter_rule_id",
                    models.BigIntegerField(blank=True, db_index=True, null=True),
                ),
                (
                    "compression_level",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("fast", "Fast"),
                            ("balanced", "Balanced"),
                            ("best", "Best"),
                        ],
                        default="balanced",
                        max_length=20,
                    ),
                ),
                ("recovery_plan_enabled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "protection_backup_config",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="BackupConfigDirectory",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("path", models.CharField(max_length=1000)),
                ("display_name", models.CharField(blank=True, default="", max_length=300)),
                ("estimated_size_bytes", models.BigIntegerField(default=0)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "backup_config",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="directories",
                        to="protection.backupconfig",
                    ),
                ),
            ],
            options={
                "db_table": "protection_backup_config_directory",
                "ordering": ["backup_config_id", "sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="BackupSourceSnapshot",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("snapshot_uid", models.CharField(max_length=64)),
                ("idempotency_key", models.CharField(max_length=128)),
                ("source_type", models.CharField(max_length=16)),
                ("source_ref_id", models.BigIntegerField()),
                ("backup_config_id", models.BigIntegerField(db_index=True)),
                ("repository_id", models.BigIntegerField(db_index=True)),
                ("task_id", models.BigIntegerField(db_index=True)),
                ("task_uuid", models.UUIDField(default=uuid.uuid4, db_index=True)),
                (
                    "trigger_type",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("schedule", "Schedule"),
                            ("retry", "Retry"),
                            ("api", "API"),
                        ],
                        default="manual",
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("creating", "Creating"),
                            ("available", "Available"),
                            ("partial", "Partial"),
                            ("failed", "Failed"),
                            ("deleting", "Deleting"),
                            ("deleted", "Deleted"),
                        ],
                        default="creating",
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("directory_count", models.IntegerField(default=0)),
                ("successful_directory_count", models.IntegerField(default=0)),
                ("failed_directory_count", models.IntegerField(default=0)),
                ("total_size_bytes", models.BigIntegerField(default=0)),
                ("file_count", models.BigIntegerField(default=0)),
                ("dir_count", models.BigIntegerField(default=0)),
                ("error_code", models.CharField(blank=True, default="", max_length=80)),
                ("error_message", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "protection_backup_source_snapshot",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="BackupSourceSnapshotDirectory",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("backup_config_id", models.BigIntegerField(db_index=True)),
                ("backup_config_dir_id", models.BigIntegerField(db_index=True)),
                ("source_path", models.CharField(max_length=1000)),
                ("display_name", models.CharField(max_length=300, blank=True, default="")),
                ("repository_id", models.BigIntegerField(db_index=True)),
                (
                    "kopia_snapshot_id",
                    models.CharField(max_length=128, blank=True, null=True, db_index=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("creating", "Creating"),
                            ("available", "Available"),
                            ("failed", "Failed"),
                            ("deleted", "Deleted"),
                        ],
                        default="creating",
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("file_count", models.BigIntegerField(default=0)),
                ("dir_count", models.BigIntegerField(default=0)),
                ("stats", models.JSONField(blank=True, default=dict)),
                ("error_code", models.CharField(max_length=80, blank=True, default="")),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="directories",
                        to="protection.backupsourcesnapshot",
                    ),
                ),
            ],
            options={
                "db_table": "protection_backup_source_snapshot_directory",
                "ordering": ["source_snapshot_id", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="backuppolicy",
            index=models.Index(
                fields=["organization_id", "is_active", "created_at"],
                name="prot_bpol_org_act_cr_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="backuppolicy",
            constraint=models.UniqueConstraint(
                fields=("organization_id", "name"),
                name="uniq_prot_bpol_org_name",
            ),
        ),
        migrations.AddIndex(
            model_name="filefilterrule",
            index=models.Index(
                fields=["organization_id", "is_active", "created_at"],
                name="prot_ffr_org_act_cr_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="filefilterrule",
            constraint=models.UniqueConstraint(
                fields=("organization_id", "name"),
                name="uniq_prot_ffr_org_name",
            ),
        ),
        migrations.AddIndex(
            model_name="backupconfig",
            index=models.Index(
                fields=["organization_id", "created_at"],
                name="prot_bcfg_org_cr_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="backupconfig",
            index=models.Index(
                fields=["organization_id", "source_type", "source_ref_id"],
                name="prot_bcfg_org_src_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="backupconfig",
            constraint=models.UniqueConstraint(
                fields=("organization_id", "name"),
                name="uniq_prot_bcfg_org_name",
            ),
        ),
        migrations.AddIndex(
            model_name="backupconfigdirectory",
            index=models.Index(
                fields=["backup_config", "path"],
                name="prot_bcdir_cfg_path_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="backupconfigdirectory",
            constraint=models.UniqueConstraint(
                fields=("backup_config", "path"),
                name="uniq_prot_bcdir_path",
            ),
        ),
        migrations.AddIndex(
            model_name="backupsourcesnapshot",
            index=models.Index(
                fields=["organization_id", "source_type", "source_ref_id", "created_at"],
                name="prot_bsrcsnap_org_src_cr_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="backupsourcesnapshot",
            index=models.Index(
                fields=["organization_id", "backup_config_id", "created_at"],
                name="prot_bsrcsnap_org_cfg_cr_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="backupsourcesnapshot",
            index=models.Index(
                fields=["organization_id", "status", "created_at"],
                name="prot_bsrcsnap_org_st_cr_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="backupsourcesnapshot",
            constraint=models.UniqueConstraint(
                fields=("organization_id", "snapshot_uid"),
                name="uniq_prot_bsrcsnap_uid",
            ),
        ),
        migrations.AddConstraint(
            model_name="backupsourcesnapshot",
            constraint=models.UniqueConstraint(
                fields=("organization_id", "idempotency_key"),
                name="uniq_prot_bsrcsnap_idem",
            ),
        ),
        migrations.AddIndex(
            model_name="backupsourcesnapshotdirectory",
            index=models.Index(
                fields=["organization_id", "backup_config_dir_id", "created_at"],
                name="prot_bssd_org_cfg_cr_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="backupsourcesnapshotdirectory",
            index=models.Index(
                fields=["organization_id", "repository_id", "kopia_snapshot_id"],
                name="prot_bssd_org_repo_kid_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="backupsourcesnapshotdirectory",
            constraint=models.UniqueConstraint(
                fields=("source_snapshot", "backup_config_dir_id"),
                name="uniq_prot_bsrcsnapdir_cfgdir",
            ),
        ),
    ]
