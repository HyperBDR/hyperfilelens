from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restore", "0002_restore_item_progress_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="restoreplan",
            name="scope",
            field=models.CharField(
                choices=[("snapshot", "Snapshot"), ("paths", "Paths")],
                default="paths",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="restoreplan",
            name="backup_config_dir_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="restoreplan",
            name="source_path",
            field=models.CharField(blank=True, default="", max_length=1000),
        ),
    ]
