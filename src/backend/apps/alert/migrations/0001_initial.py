from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("iam", "0001_initial"),
        ("notification", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertRule",
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
                ("name", models.CharField(max_length=200)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "severity",
                    models.CharField(
                        db_index=True,
                        default="warning",
                        help_text="info|warning|critical",
                        max_length=20,
                    ),
                ),
                (
                    "trigger",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Trigger definition, e.g. {type: 'task_failed'}",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alert_rules",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "alerts_rule",
                "ordering": ["-updated_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="Alert",
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
                ("severity", models.CharField(db_index=True, default="warning", max_length=20)),
                ("title", models.CharField(max_length=300)),
                ("message", models.TextField(blank=True, default="")),
                ("context", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("acked", "Acked"), ("resolved", "Resolved")],
                        db_index=True,
                        default="open",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("acked_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alerts",
                        to="iam.organization",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="alerts",
                        to="alerts.alertrule",
                    ),
                ),
            ],
            options={
                "db_table": "alerts_alert",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="alertrule",
            name="channels",
            field=models.ManyToManyField(
                blank=True,
                related_name="rules",
                to="notification.notificationchannel",
            ),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["organization", "status", "created_at"],
                name="alerts_aler_organ_8dd9da_idx",
            ),
        ),
    ]
