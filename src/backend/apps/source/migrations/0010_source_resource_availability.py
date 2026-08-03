from datetime import timedelta

import django.utils.timezone
from django.db import migrations, models


MOUNT_RESOURCE_TYPES = frozenset({"nas", "nfs", "cifs"})


def _latest_timestamp(*values):
    available = [value for value in values if value is not None]
    return max(available) if available else None


def backfill_source_availability(apps, schema_editor):
    del schema_editor
    SourceResource = apps.get_model("source", "SourceResource")
    now = django.utils.timezone.now()
    fresh_cutoff = now - timedelta(minutes=15)

    resources = SourceResource.objects.select_related("bound_node").all()
    for resource in resources.iterator(chunk_size=500):
        availability = "offline"
        observed_at = now
        node = resource.bound_node

        if resource.resource_type == "local" and node is not None:
            availability = node.availability
            observed_at = node.availability_updated_at or now
        elif resource.resource_type in MOUNT_RESOURCE_TYPES and node is not None:
            proxy_online = node.availability == "online"
            fresh_probe = (
                resource.connection_test_status == "success"
                and resource.last_connection_test is not None
                and resource.last_connection_test >= fresh_cutoff
            )
            fresh_mount = (
                resource.mount_status == "mounted"
                and resource.updated_at is not None
                and resource.updated_at >= fresh_cutoff
            )
            if proxy_online and (fresh_probe or fresh_mount):
                availability = "online"
                observed_at = _latest_timestamp(
                    resource.last_connection_test if fresh_probe else None,
                    resource.updated_at if fresh_mount else None,
                ) or now

        resource.availability = availability
        resource.availability_updated_at = observed_at
        resource.save(
            update_fields=["availability", "availability_updated_at"],
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("node", "0009_node_availability"),
        ("source", "0009_repository_purge_pending_idempotency_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourceresource",
            name="availability",
            field=models.CharField(
                choices=[("online", "Online"), ("offline", "Offline")],
                db_index=True,
                default="offline",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="sourceresource",
            name="availability_updated_at",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
            ),
        ),
        migrations.RunPython(
            backfill_source_availability,
            migrations.RunPython.noop,
        ),
    ]
