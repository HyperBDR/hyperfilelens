import hashlib

from django.db import migrations, models


def _pending_key(row) -> str | None:
    payload = row.payload if isinstance(row.payload, dict) else {}
    raw_snapshot_ids = payload.get("source_snapshot_ids")
    if not isinstance(raw_snapshot_ids, (list, tuple, set)):
        return None
    snapshot_ids = set()
    for value in raw_snapshot_ids:
        try:
            snapshot_id = int(value)
        except (TypeError, ValueError):
            continue
        if snapshot_id > 0:
            snapshot_ids.add(snapshot_id)
    if not snapshot_ids:
        return None
    normalized_snapshot_ids = sorted(snapshot_ids)
    identity = ":".join(
        [
            str(row.organization_id),
            str(row.source_kind),
            str(row.source_ref_id),
            str(row.repository_id),
            ",".join(str(value) for value in normalized_snapshot_ids),
        ]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def backfill_pending_keys(apps, schema_editor):
    pending_model = apps.get_model(
        "source",
        "BackupSourceRepositoryPurgePending",
    )
    canonical_by_key = {}
    rows = pending_model.objects.order_by("id").all()
    for row in rows.iterator(chunk_size=500):
        key = _pending_key(row)
        if key is None:
            continue
        canonical = canonical_by_key.get(key)
        if canonical is None:
            row.idempotency_key = key
            row.save(update_fields=["idempotency_key"])
            canonical_by_key[key] = row
            continue

        canonical_payload = (
            dict(canonical.payload)
            if isinstance(canonical.payload, dict)
            else {}
        )
        duplicate_payload = row.payload if isinstance(row.payload, dict) else {}
        canonical_payload["kopia_snapshot_ids"] = list(
            dict.fromkeys(
                [
                    *(canonical_payload.get("kopia_snapshot_ids") or []),
                    *(duplicate_payload.get("kopia_snapshot_ids") or []),
                ]
            )
        )
        canonical.payload = canonical_payload
        canonical.retry_count = max(
            int(canonical.retry_count or 0),
            int(row.retry_count or 0),
        )
        if row.last_error:
            canonical.last_error = row.last_error
        canonical.save(
            update_fields=["payload", "retry_count", "last_error", "updated_at"]
        )
        row.delete()


class Migration(migrations.Migration):
    dependencies = [("source", "0008_encrypt_source_credentials")]

    operations = [
        migrations.AddField(
            model_name="backupsourcerepositorypurgepending",
            name="idempotency_key",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(
            backfill_pending_keys,
            migrations.RunPython.noop,
        ),
    ]
