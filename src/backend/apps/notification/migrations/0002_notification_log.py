# Generated manually

import uuid

import django.db.models.deletion
from django.db import migrations, models


# Supports DBs that still use legacy `notifications_*` tables from the old app label.
_NOTIFICATION_0002_FORWARD = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'notifications_channel'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'notification_channel'
    ) THEN
        ALTER TABLE notifications_channel RENAME TO notification_channel;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'notifications_delivery'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'notification_delivery'
    ) THEN
        ALTER TABLE notifications_delivery RENAME TO notification_delivery;
    END IF;
END $$;

ALTER TABLE notification_channel
    ALTER COLUMN channel_type TYPE varchar(50) USING channel_type::varchar(50);
CREATE INDEX IF NOT EXISTS notification_channel_channel_type_idx
    ON notification_channel (channel_type);

CREATE TABLE IF NOT EXISTS notification_log (
    id uuid PRIMARY KEY,
    alert_record_id uuid NULL,
    event_type varchar(120) NOT NULL DEFAULT '',
    notification_type varchar(50) NOT NULL DEFAULT 'firing',
    status varchar(50) NOT NULL,
    error_message text NOT NULL DEFAULT '',
    payload jsonb NOT NULL DEFAULT '{}',
    sent_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    channel_id bigint NOT NULL REFERENCES notification_channel(id) DEFERRABLE INITIALLY DEFERRED,
    organization_id bigint NOT NULL REFERENCES iam_organization(id) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS notification_log_alert_record_id_idx
    ON notification_log (alert_record_id);
CREATE INDEX IF NOT EXISTS notification_log_event_type_idx
    ON notification_log (event_type);
CREATE INDEX IF NOT EXISTS notification_log_sent_at_idx
    ON notification_log (sent_at);
CREATE INDEX IF NOT EXISTS notif_log_org_st_sent_idx
    ON notification_log (organization_id, status, sent_at);
"""

_NOTIFICATION_0002_REVERSE = """
DROP INDEX IF EXISTS notif_log_org_st_sent_idx;
DROP TABLE IF EXISTS notification_log;
DROP INDEX IF EXISTS notification_channel_channel_type_idx;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("notification", "0001_initial"),
        ("iam", "0001_initial"),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="notificationchannel",
            name="channel_type",
            field=models.CharField(
                choices=[
                    ("email", "Email"),
                    ("webhook", "Webhook"),
                    ("dingtalk", "DingTalk"),
                    ("wecom", "WeCom"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
        migrations.CreateModel(
            name="NotificationLog",
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
                ("alert_record_id", models.UUIDField(blank=True, db_index=True, null=True)),
                (
                    "event_type",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=120
                    ),
                ),
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
                ("payload", models.JSONField(blank=True, default=dict)),
                ("sent_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="notification.notificationchannel",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_logs",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "notification_log",
                "ordering": ["-sent_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="notificationlog",
            index=models.Index(
                fields=["organization", "status", "sent_at"],
                name="notif_log_org_st_sent_idx",
            ),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=_NOTIFICATION_0002_FORWARD,
                    reverse_sql=_NOTIFICATION_0002_REVERSE,
                ),
            ],
            state_operations=state_operations,
        ),
    ]
