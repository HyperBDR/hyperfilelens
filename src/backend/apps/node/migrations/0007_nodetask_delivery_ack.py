from __future__ import annotations

from django.db import migrations, models
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def backfill_cancel_requested_at(apps, schema_editor):
    NodeTask = apps.get_model("node", "NodeTask")
    active_statuses = ("pending", "running")
    for task in NodeTask.objects.filter(status__in=active_statuses).iterator(chunk_size=500):
        result = task.result if isinstance(task.result, dict) else {}
        if result.get("cancel_requested") is not True:
            continue
        raw = result.get("cancel_requested_at")
        parsed = parse_datetime(str(raw)) if raw else None
        if parsed is not None and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        task.cancel_requested_at = parsed or task.updated_at
        task.save(update_fields=["cancel_requested_at"])


class Migration(migrations.Migration):
    dependencies = [("node", "0006_node_network_inventory")]

    operations = [
        migrations.AddField(
            model_name="nodetask",
            name="accepted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="nodetask",
            name="last_delivery_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="nodetask",
            name="delivery_attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="nodetask",
            name="cancel_requested_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(backfill_cancel_requested_at, migrations.RunPython.noop),
    ]
