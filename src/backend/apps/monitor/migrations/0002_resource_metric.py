import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("iam", "0001_initial"),
        ("monitor", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResourceMetric",
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
                ("resource_type", models.CharField(db_index=True, max_length=100)),
                ("resource_id", models.CharField(db_index=True, max_length=128)),
                ("resource_name", models.CharField(blank=True, default="", max_length=255)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("heartbeat", "Heartbeat"),
                            ("collector", "Collector"),
                            ("system", "System"),
                        ],
                        db_index=True,
                        default="heartbeat",
                        max_length=32,
                    ),
                ),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resource_metrics",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "monitor_resource_metric",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="resourcemetric",
            index=models.Index(
                fields=["organization", "resource_type", "resource_id", "-timestamp"],
                name="mon_res_org_type_id_ts_idx",
            ),
        ),
    ]
