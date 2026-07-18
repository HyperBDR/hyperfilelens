from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0009_backup_directory_orchestrator_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="last_progress_sample",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
