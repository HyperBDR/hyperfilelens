from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0005_remove_backup_config_name_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="filefilterrule",
            name="add_dot_ignore_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="filefilterrule",
            name="dot_ignore_filenames",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="filefilterrule",
            name="error_handling",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
