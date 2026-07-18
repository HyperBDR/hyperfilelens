from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0007_backup_path_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupconfig",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("resetting", "Resetting"),
                    ("reset_failed", "Reset failed"),
                ],
                db_index=True,
                default="active",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="backupconfig",
            name="reset_task_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
