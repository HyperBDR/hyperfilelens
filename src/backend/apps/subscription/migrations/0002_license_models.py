import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("subscription", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="License",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("license_key", models.CharField(db_index=True, max_length=64, unique=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("change_type", models.CharField(default="initial", max_length=20)),
                ("change_reason", models.CharField(blank=True, default="", max_length=200)),
                ("machine_code", models.CharField(db_index=True, max_length=64)),
                ("max_organizations", models.IntegerField(default=1)),
                ("max_users", models.IntegerField(default=50)),
                ("max_nodes", models.IntegerField(default=20)),
                ("max_storage_gb", models.IntegerField(default=500)),
                ("max_gateways", models.IntegerField(default=5)),
                ("ai_insights_quota", models.IntegerField(default=500)),
                ("max_tasks", models.IntegerField(default=50)),
                ("max_alert_policies", models.IntegerField(default=50)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("activated_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("signature", models.TextField(blank=True, default="")),
                ("status", models.CharField(db_index=True, default="active", max_length=20)),
                (
                    "activated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activated_licenses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="license",
                        to="iam.organization",
                    ),
                ),
            ],
            options={"db_table": "subscription_license", "ordering": ["-activated_at"]},
        ),
        migrations.CreateModel(
            name="LicenseHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("license_key", models.CharField(db_index=True, max_length=64)),
                ("version", models.PositiveIntegerField(default=1)),
                ("machine_code", models.CharField(max_length=64)),
                ("max_organizations", models.IntegerField()),
                ("max_users", models.IntegerField()),
                ("max_nodes", models.IntegerField()),
                ("max_storage_gb", models.IntegerField()),
                ("max_gateways", models.IntegerField()),
                ("ai_insights_quota", models.IntegerField()),
                ("max_tasks", models.IntegerField()),
                ("max_alert_policies", models.IntegerField()),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("activated_at", models.DateTimeField()),
                ("archived_at", models.DateTimeField()),
                ("status", models.CharField(max_length=20)),
                ("signature", models.TextField(blank=True, default="")),
                ("change_type", models.CharField(max_length=20)),
                ("change_reason", models.CharField(blank=True, default="", max_length=200)),
                (
                    "activated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="license_history_activated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="license_history_changed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="license_history",
                        to="iam.organization",
                    ),
                ),
            ],
            options={"db_table": "subscription_license_history", "ordering": ["-archived_at"]},
        ),
        migrations.CreateModel(
            name="MachineCode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=64, unique=True)),
                ("hostname", models.CharField(blank=True, default="", max_length=100)),
                ("source", models.CharField(blank=True, default="", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="machine_code_record",
                        to="iam.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="machine_codes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "subscription_machine_code", "ordering": ["-created_at"]},
        ),
    ]
