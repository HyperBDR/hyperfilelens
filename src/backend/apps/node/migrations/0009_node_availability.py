from datetime import timedelta

import django.utils.timezone
from django.db import migrations, models
from django.db.models import F


def backfill_node_availability(apps, schema_editor):
    del schema_editor
    Node = apps.get_model("node", "Node")
    now = django.utils.timezone.now()
    fresh_cutoff = now - timedelta(seconds=90)

    Node.objects.all().update(
        availability="offline",
        availability_updated_at=now,
    )
    Node.objects.filter(
        status="online",
        last_seen_at__gte=fresh_cutoff,
    ).update(
        availability="online",
        availability_updated_at=F("last_seen_at"),
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("node", "0008_nodetask_requesting_organization")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="availability",
            field=models.CharField(
                choices=[("online", "Online"), ("offline", "Offline")],
                db_index=True,
                default="offline",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="availability_updated_at",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
            ),
        ),
        migrations.RunPython(
            backfill_node_availability,
            migrations.RunPython.noop,
        ),
    ]
