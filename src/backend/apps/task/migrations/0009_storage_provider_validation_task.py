from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("task", "0008_task_recovery_chain")]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="organization_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
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
                    ("repository_operation", "Repository operation"),
                    ("storage_provider_validation", "Storage provider validation"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
