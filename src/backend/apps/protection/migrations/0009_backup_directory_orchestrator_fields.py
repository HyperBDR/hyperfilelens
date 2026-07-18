from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0008_backup_config_reset_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="adopted_late_result",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="cancel_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="dispatched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="last_progress_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="last_substantive_progress_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="node_task_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="retry_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="stall_warned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="backupsourcesnapshotdirectory",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("dispatching", "Dispatching"),
                    ("running", "Running"),
                    ("creating", "Creating"),
                    ("available", "Available"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                    ("deleted", "Deleted"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
    ]
