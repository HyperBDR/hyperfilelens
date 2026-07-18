from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("task", "0004_backup_config_reset_task_type"),
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
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
