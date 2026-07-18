from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("source", "0003_normalize_backup_pipeline_steps"),
    ]

    operations = [
        migrations.CreateModel(
            name="BackupSourceRepositoryPurgePending",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("source_kind", models.CharField(db_index=True, max_length=16)),
                ("source_ref_id", models.BigIntegerField(db_index=True)),
                ("repository_id", models.BigIntegerField(db_index=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "source_repository_purge_pending",
                "indexes": [
                    models.Index(
                        fields=["organization_id", "repository_id", "created_at"],
                        name="src_repo_purge_org_repo_idx",
                    )
                ],
            },
        ),
    ]
