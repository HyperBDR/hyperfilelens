from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("task", "0003_snapshot_delete_task_type"),
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
                ],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="taskresource",
            name="resource_type",
            field=models.CharField(
                choices=[
                    ("backup_source", "Backup source"),
                    ("backup_config", "Backup config"),
                    ("repository", "Repository"),
                    ("target_repository", "Target repository"),
                    ("snapshot", "Snapshot"),
                    ("host", "Host"),
                    ("volume", "Volume"),
                ],
                max_length=32,
            ),
        ),
    ]
