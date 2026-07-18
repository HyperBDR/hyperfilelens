import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SystemMetric",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("cpu", models.JSONField(blank=True, default=dict)),
                ("memory", models.JSONField(blank=True, default=dict)),
                ("swap", models.JSONField(blank=True, default=dict)),
                ("disks", models.JSONField(blank=True, default=list)),
                ("disk_io", models.JSONField(blank=True, default=list)),
                ("networks", models.JSONField(blank=True, default=list)),
                ("load_average", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "System metric",
                "verbose_name_plural": "System metrics",
                "db_table": "monitor_system_metric",
                "ordering": ["-timestamp"],
            },
        ),
    ]
