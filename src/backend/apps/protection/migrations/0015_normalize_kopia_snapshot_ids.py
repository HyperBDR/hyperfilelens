from django.db import migrations


def normalize_legacy_kopia_snapshot_ids(apps, _schema_editor):
    SnapshotDirectory = apps.get_model(
        "protection", "BackupSourceSnapshotDirectory"
    )
    rows = SnapshotDirectory.objects.exclude(kopia_snapshot_id__isnull=True).only(
        "id", "kopia_snapshot_id"
    )
    updates = []
    for row in rows.iterator(chunk_size=1000):
        if str(row.kopia_snapshot_id or "").strip().lower() not in {"none", "null"}:
            continue
        row.kopia_snapshot_id = None
        updates.append(row)
        if len(updates) >= 1000:
            SnapshotDirectory.objects.bulk_update(
                updates, ["kopia_snapshot_id"], batch_size=1000
            )
            updates.clear()
    if updates:
        SnapshotDirectory.objects.bulk_update(
            updates, ["kopia_snapshot_id"], batch_size=1000
        )


class Migration(migrations.Migration):
    dependencies = [("protection", "0014_backup_source_snapshot_delete_failed")]

    operations = [
        migrations.RunPython(
            normalize_legacy_kopia_snapshot_ids,
            migrations.RunPython.noop,
        )
    ]
