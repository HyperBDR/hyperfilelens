"""Add resumable enrollment sessions and per-node credentials."""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("node", "0009_node_availability"),
    ]

    operations = [
        migrations.AddField(
            model_name="node",
            name="installation_id",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=128
            ),
        ),
        migrations.AddConstraint(
            model_name="node",
            constraint=models.UniqueConstraint(
                condition=Q(is_deleted=False) & ~Q(installation_id=""),
                fields=("organization", "role", "installation_id"),
                name="node_unique_installation_identity",
            ),
        ),
        migrations.AddField(
            model_name="nodetoken",
            name="enrollment_mode",
            field=models.CharField(
                choices=[("legacy", "Legacy"), ("current", "Current")],
                db_index=True,
                default="legacy",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="nodetoken",
            name="enrollment_mode",
            field=models.CharField(
                choices=[("legacy", "Legacy"), ("current", "Current")],
                db_index=True,
                default="current",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="NodeCredential",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("agent", "Agent"),
                            ("proxy", "Proxy"),
                            ("gateway", "Gateway"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "installation_id",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=128
                    ),
                ),
                ("secret_prefix", models.CharField(db_index=True, max_length=16)),
                ("secret_hash", models.CharField(max_length=64, unique=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "enrollment_token",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="issued_credentials",
                        to="node.nodetoken",
                    ),
                ),
                (
                    "node",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credential",
                        to="node.node",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="node_credentials",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "node_credentials",
                "ordering": ["organization_id", "node_id"],
            },
        ),
        migrations.CreateModel(
            name="NodeInstallationSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("agent", "Agent"),
                            ("proxy", "Proxy"),
                            ("gateway", "Gateway"),
                        ],
                        max_length=20,
                    ),
                ),
                ("installation_id", models.CharField(db_index=True, max_length=128)),
                ("secret_prefix", models.CharField(db_index=True, max_length=16)),
                ("secret_hash", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("released", "Released"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=16,
                    ),
                ),
                (
                    "last_activity_at",
                    models.DateTimeField(db_index=True, default=timezone.now),
                ),
                ("idle_expires_at", models.DateTimeField(db_index=True)),
                ("absolute_expires_at", models.DateTimeField(db_index=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "enrollment_token",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="installation_sessions",
                        to="node.nodetoken",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="node_installation_sessions",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "node_installation_sessions",
                "ordering": ["-created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["enrollment_token", "status", "idle_expires_at"],
                        name="node_inst_session_active_idx",
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="nodeinstallationsession",
            constraint=models.UniqueConstraint(
                condition=Q(status="active"),
                fields=("enrollment_token", "role", "installation_id"),
                name="node_inst_session_active_uniq",
            ),
        ),
    ]
