from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationChannel",
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
                (
                    "channel_type",
                    models.CharField(
                        choices=[("email", "Email"), ("webhook", "Webhook")],
                        max_length=20,
                    ),
                ),
                ("config", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_channels",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "notification_channel",
                "ordering": ["organization_id", "name", "id"],
            },
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
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
                ("event_type", models.CharField(db_index=True, max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error", models.TextField(blank=True, default="")),
                ("sent_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="notification.notificationchannel",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_deliveries",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "notification_delivery",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["organization", "status", "created_at"],
                name="notification_del_organ_5a47c0_idx",
            ),
        ),
    ]
