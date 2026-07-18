# Generated manually for alert center refactor

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0001_initial"),
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="alertrule",
            name="channels",
        ),
        migrations.DeleteModel(
            name="Alert",
        ),
        migrations.DeleteModel(
            name="AlertRule",
        ),
        migrations.CreateModel(
            name="AlertPolicy",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("metric", "Metric Alert"),
                            ("availability", "Availability Alert"),
                            ("task", "Task Alert"),
                            ("event", "Event Alert"),
                            ("system", "System Alert"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("critical", "Critical"),
                            ("warning", "Warning"),
                            ("info", "Info"),
                        ],
                        max_length=50,
                    ),
                ),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                (
                    "resource_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("system", "System"),
                            ("sync_proxy", "Sync Proxy"),
                            ("gateway", "Gateway"),
                            ("agent_proxy", "Agent Proxy"),
                            ("backup_repository", "Backup Repository"),
                            ("source_resource", "Source Resource"),
                            ("target_storage", "Target Storage"),
                            ("task", "Task"),
                            ("system_service", "System Service"),
                            ("license", "License"),
                            ("user", "User"),
                        ],
                        default="",
                        max_length=100,
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[("all", "All"), ("selected", "Selected")],
                        default="selected",
                        max_length=50,
                    ),
                ),
                ("resource_ids", models.JSONField(blank=True, default=list)),
                ("trigger_rule", models.JSONField(default=dict)),
                ("recovery_rule", models.JSONField(blank=True, null=True)),
                ("notification_channel_ids", models.JSONField(blank=True, default=list)),
                ("created_by", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alert_policies",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "alert_policies",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AlertRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("policy_id", models.UUIDField(blank=True, db_index=True, null=True)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("metric", "Metric Alert"),
                            ("availability", "Availability Alert"),
                            ("task", "Task Alert"),
                            ("event", "Event Alert"),
                            ("system", "System Alert"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("critical", "Critical"),
                            ("warning", "Warning"),
                            ("info", "Info"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("firing", "Firing"),
                            ("acknowledged", "Acknowledged"),
                            ("resolved", "Resolved"),
                        ],
                        db_index=True,
                        default="firing",
                        max_length=50,
                    ),
                ),
                (
                    "resource_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("system", "System"),
                            ("sync_proxy", "Sync Proxy"),
                            ("gateway", "Gateway"),
                            ("agent_proxy", "Agent Proxy"),
                            ("backup_repository", "Backup Repository"),
                            ("source_resource", "Source Resource"),
                            ("target_storage", "Target Storage"),
                            ("task", "Task"),
                            ("system_service", "System Service"),
                            ("license", "License"),
                            ("user", "User"),
                        ],
                        default="",
                        max_length=100,
                    ),
                ),
                ("resource_id", models.CharField(blank=True, default="", max_length=64)),
                ("resource_name", models.CharField(blank=True, default="", max_length=255)),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField(blank=True, default="")),
                (
                    "current_value",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=20, null=True
                    ),
                ),
                (
                    "threshold_value",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=20, null=True
                    ),
                ),
                ("unit", models.CharField(blank=True, default="", max_length=50)),
                ("fingerprint", models.CharField(db_index=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("first_triggered_at", models.DateTimeField(blank=True, null=True)),
                ("last_triggered_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_by", models.BigIntegerField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alert_records",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "alert_records",
                "ordering": ["-last_triggered_at", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AlertNotificationLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("alert_record_id", models.UUIDField(db_index=True)),
                ("channel_id", models.BigIntegerField(db_index=True)),
                (
                    "notification_type",
                    models.CharField(
                        choices=[("firing", "Firing"), ("resolved", "Resolved")],
                        default="firing",
                        max_length=50,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("success", "Success"), ("failed", "Failed")],
                        max_length=50,
                    ),
                ),
                ("error_message", models.TextField(blank=True, default="")),
                ("sent_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "db_table": "alert_notification_logs",
                "ordering": ["-sent_at"],
            },
        ),
        migrations.AddIndex(
            model_name="alertpolicy",
            index=models.Index(
                fields=["organization", "enabled"], name="alert_pol_org_en_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="alertpolicy",
            index=models.Index(
                fields=["organization", "type"], name="alert_pol_org_ty_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="alertrecord",
            index=models.Index(
                fields=["organization", "status", "created_at"],
                name="alert_rec_org_st_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="alertrecord",
            index=models.Index(fields=["fingerprint"], name="alert_rec_fp_idx"),
        ),
    ]
