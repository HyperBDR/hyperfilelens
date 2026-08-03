from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("task", "0009_storage_provider_validation_task"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="task_type",
            field=models.CharField(
                choices=[
                    ("backup", "Backup"),
                    ("restore", "Restore"),
                    ("snapshot_download", "Snapshot download"),
                    ("snapshot_delete", "Snapshot delete"),
                    ("backup_config_reset", "Backup config reset"),
                    ("source_unregister", "Source unregister"),
                    ("node_lifecycle", "Node lifecycle"),
                    ("repository_operation", "Repository operation"),
                    ("storage_provider_validation", "Storage provider validation"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="taskstep",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("running", "Running"),
                    ("success", "Success"),
                    ("warning", "Warning"),
                    ("failed", "Failed"),
                    ("skipped", "Skipped"),
                ],
                db_index=True,
                default="pending",
                max_length=32,
            ),
        ),
    ]
