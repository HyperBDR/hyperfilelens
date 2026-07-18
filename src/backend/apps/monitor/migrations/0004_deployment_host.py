"""Deployment host model and host-scoped system metrics."""

import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def _assign_legacy_metrics(apps, schema_editor):
    DeploymentHost = apps.get_model("monitor", "DeploymentHost")
    SystemMetric = apps.get_model("monitor", "SystemMetric")

    if not SystemMetric.objects.filter(host__isnull=True).exists():
        return

    import platform

    host, _ = DeploymentHost.objects.get_or_create(
        hostname=platform.node(),
        defaults={
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "last_seen_at": timezone.now(),
        },
    )
    SystemMetric.objects.filter(host__isnull=True).update(host=host)


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0003_rename_monitor_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeploymentHost",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("hostname", models.CharField(db_index=True, max_length=255, unique=True)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("platform", models.CharField(blank=True, default="", max_length=255)),
                ("python_version", models.CharField(blank=True, default="", max_length=64)),
                ("app_version", models.CharField(blank=True, default="", max_length=64)),
                ("boot_time", models.FloatField(blank=True, null=True)),
                ("last_seen_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Deployment host",
                "verbose_name_plural": "Deployment hosts",
                "db_table": "monitor_deployment_hosts",
                "ordering": ["-last_seen_at", "hostname"],
            },
        ),
        migrations.AddField(
            model_name="systemmetric",
            name="host",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="metrics",
                to="monitor.deploymenthost",
            ),
        ),
        migrations.RunPython(_assign_legacy_metrics, migrations.RunPython.noop),
    ]
