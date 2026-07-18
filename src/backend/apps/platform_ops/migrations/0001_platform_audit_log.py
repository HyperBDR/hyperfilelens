# Generated manually for PlatformAuditLog

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(db_index=True, max_length=80)),
                ("target_type", models.CharField(db_index=True, max_length=80)),
                ("target_id", models.CharField(blank=True, default="", max_length=120)),
                ("org_key", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=512)),
                (
                    "result",
                    models.CharField(
                        choices=[("success", "Success"), ("failure", "Failure")],
                        db_index=True,
                        default="success",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="platform_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "platform_ops_audit_log",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["action", "created_at"], name="platform_op_action_6a0f0d_idx"),
                    models.Index(fields=["target_type", "created_at"], name="platform_op_target__f8d4b2_idx"),
                ],
            },
        ),
    ]
