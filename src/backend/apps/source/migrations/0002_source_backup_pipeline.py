import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0001_initial"),
        ("source", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SourceBackupPipelineEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("source_kind", models.CharField(choices=[("agent", "Agent"), ("nas", "NAS")], max_length=16)),
                ("ref_id", models.BigIntegerField()),
                (
                    "step",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "Backup source pool"), (2, "Backup configuration"), (3, "Ready to run backup")],
                        default=1,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="source_backup_pipeline_entries",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "source_backup_pipeline",
                "ordering": ["-updated_at", "-id"],
                "indexes": [
                    models.Index(fields=["organization", "step"], name="source_back_organiz_0f0f0f_idx"),
                    models.Index(
                        fields=["organization", "source_kind", "ref_id"],
                        name="source_back_organiz_1a1a1a_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization", "source_kind", "ref_id"),
                        name="uniq_source_backup_pipeline_org_kind_ref",
                    )
                ],
            },
        ),
    ]
