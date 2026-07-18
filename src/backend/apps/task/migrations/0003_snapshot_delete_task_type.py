from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("task", "0002_task_resource_subtype_and_terminal_progress"),
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
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
