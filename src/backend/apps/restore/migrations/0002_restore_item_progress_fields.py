
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restore", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="restorerecorditem",
            name="node_task_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="restorerecorditem",
            name="last_progress_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="restorerecorditem",
            name="last_progress_sample",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
