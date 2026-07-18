from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("task", "0001_initial"),
        ("protection", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SnapshotDownloadArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("source_snapshot_directory_id", models.BigIntegerField(db_index=True)),
                ("relative_path", models.CharField(max_length=1000)),
                ("filename", models.CharField(max_length=300)),
                ("content_type", models.CharField(default="application/octet-stream", max_length=120)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("storage_path", models.CharField(max_length=1200)),
                (
                    "status",
                    models.CharField(
                        choices=[("ready", "Ready"), ("expired", "Expired"), ("deleted", "Deleted")],
                        db_index=True,
                        default="ready",
                        max_length=20,
                    ),
                ),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("downloaded_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "task",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="snapshot_download_artifact",
                        to="task.task",
                    ),
                ),
            ],
            options={
                "db_table": "protection_snapshot_download_artifact",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="snapshotdownloadartifact",
            index=models.Index(fields=["organization_id", "status", "expires_at"], name="prot_snapdl_org_st_exp_idx"),
        ),
        migrations.AddIndex(
            model_name="snapshotdownloadartifact",
            index=models.Index(
                fields=["organization_id", "source_snapshot_directory_id", "created_at"],
                name="prot_snapdl_org_dir_cr_idx",
            ),
        ),
    ]
