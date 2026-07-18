from decimal import Decimal

from django.db import migrations, models


def backfill_task_resource_subtype(apps, schema_editor):
    TaskResource = apps.get_model("task", "TaskResource")
    rows = (
        TaskResource.objects.select_related("task")
        .filter(resource_type="backup_source", resource_subtype="")
        .only("id", "resource_subtype", "task__request_payload")
    )
    updates = []
    for row in rows.iterator():
        payload = row.task.request_payload if row.task else None
        source_type = ""
        if isinstance(payload, dict):
            source_type = str(payload.get("source_type") or "").strip().lower()
        if source_type in {"agent", "nas"}:
            row.resource_subtype = source_type
            updates.append(row)
    if updates:
        TaskResource.objects.bulk_update(updates, ["resource_subtype"], batch_size=500)


def repair_terminal_failure_progress(apps, schema_editor):
    Task = apps.get_model("task", "Task")
    rows = Task.objects.filter(
        status__in=["failed", "timeout", "cancelled"],
        progress=Decimal("100.00"),
    ).only("id", "task_type", "current_step", "progress")
    updates = []
    for row in rows.iterator():
        step = str(row.current_step or "").strip()
        if step in {"dispatch_agent"}:
            row.progress = Decimal("45.00")
        elif step in {"snapshot_download_restore", "restore"} and row.task_type == "snapshot_download":
            row.progress = Decimal("10.00")
        elif step in {"snapshot_download_transfer", "transfer"}:
            row.progress = Decimal("70.00")
        elif step in {"snapshot_download_finalize", "finalize"} and row.task_type == "snapshot_download":
            row.progress = Decimal("90.00")
        elif step in {"create_logic_snapshot", "kopia_snapshot"}:
            row.progress = Decimal("95.00")
        elif step in {"restore", "finalize", "finalize_snapshot"}:
            row.progress = Decimal("95.00")
        else:
            row.progress = Decimal("95.00")
        updates.append(row)
    if updates:
        Task.objects.bulk_update(updates, ["progress"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("task", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="taskresource",
            name="resource_subtype",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.RunPython(backfill_task_resource_subtype, migrations.RunPython.noop),
        migrations.RunPython(repair_terminal_failure_progress, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="taskresource",
            name="uniq_task_resource",
        ),
        migrations.RemoveIndex(
            model_name="taskresource",
            name="task_resource_lookup_idx",
        ),
        migrations.AddIndex(
            model_name="taskresource",
            index=models.Index(
                fields=["resource_type", "resource_subtype", "resource_id"],
                name="task_resource_lookup_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="taskresource",
            constraint=models.UniqueConstraint(
                fields=("task", "resource_type", "resource_subtype", "resource_id"),
                name="uniq_task_resource_subtype",
            ),
        ),
    ]
