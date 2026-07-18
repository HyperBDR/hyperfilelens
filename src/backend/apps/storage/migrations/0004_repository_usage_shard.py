from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0003_repository_health_unverified"),
    ]

    operations = [
        migrations.CreateModel(
            name="RepositoryUsageShard",
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
                ("repository_id", models.BigIntegerField(db_index=True)),
                (
                    "usage_scope",
                    models.CharField(
                        choices=[("direct_nas_agent", "Direct NAS Agent")],
                        default="direct_nas_agent",
                        max_length=40,
                    ),
                ),
                ("node_id", models.BigIntegerField(db_index=True)),
                ("repository_subdir", models.CharField(max_length=500)),
                ("estimated_usage_bytes", models.BigIntegerField(default=0)),
                ("capacity_bytes", models.BigIntegerField(default=0)),
                ("physical_usage_bytes", models.BigIntegerField(blank=True, null=True)),
                ("source_config_count", models.IntegerField(default=0)),
                ("source_config_ids", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        db_index=True,
                        default="skipped",
                        max_length=20,
                    ),
                ),
                ("last_error", models.CharField(blank=True, default="", max_length=1000)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_checked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_success_checked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "storage_repository_usage_shard",
                "ordering": ["organization_id", "repository_id", "usage_scope", "node_id", "id"],
                "indexes": [
                    models.Index(
                        fields=["organization_id", "repository_id", "usage_scope"],
                        name="storage_rus_org_repo_scope_idx",
                    ),
                    models.Index(
                        fields=["organization_id", "node_id"],
                        name="storage_rus_org_node_idx",
                    ),
                    models.Index(fields=["last_checked_at"], name="storage_rus_checked_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "organization_id",
                            "repository_id",
                            "usage_scope",
                            "node_id",
                            "repository_subdir",
                        ],
                        name="uniq_storage_rus_scope_node",
                    ),
                ],
            },
        ),
    ]
