from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("protection", "0013_unique_active_backup_snapshot")]

    operations = [
        migrations.AlterField(
            model_name="backupsourcesnapshot",
            name="status",
            field=models.CharField(
                choices=[
                    ("creating", "Creating"),
                    ("available", "Available"),
                    ("partial", "Partial"),
                    ("failed", "Failed"),
                    ("deleting", "Deleting"),
                    ("delete_failed", "Delete failed"),
                    ("deleted", "Deleted"),
                ],
                db_index=True,
                default="creating",
                max_length=20,
            ),
        ),
    ]
