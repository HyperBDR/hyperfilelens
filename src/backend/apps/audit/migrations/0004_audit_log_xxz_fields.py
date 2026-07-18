from django.db import migrations, models
import django.utils.timezone


# Idempotent SQL for databases that already applied legacy audit migrations
# (0004_audit_result_operator / 0005_audit_diff_trace) before this file replaced them.
_AUDIT_LOG_XXZ_FORWARD = """
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_email varchar(255) NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_name varchar(255) NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS details text NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS changes jsonb NOT NULL DEFAULT '{}';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'audit_logs' AND column_name = 'result'
    ) THEN
        ALTER TABLE audit_logs
            ADD COLUMN result varchar(20) NOT NULL DEFAULT 'success';
    ELSE
        ALTER TABLE audit_logs
            ALTER COLUMN result TYPE varchar(20) USING result::varchar(20);
        ALTER TABLE audit_logs
            ALTER COLUMN result SET DEFAULT 'success';
    END IF;
END $$;

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS error_message text NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS error_code varchar(50) NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_method varchar(10) NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_path varchar(1000) NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_query jsonb NOT NULL DEFAULT '{}';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_body jsonb NOT NULL DEFAULT '{}';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_id varchar(100) NOT NULL DEFAULT '';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS session_id varchar(100) NOT NULL DEFAULT '';

ALTER TABLE audit_logs
    ALTER COLUMN user_agent TYPE varchar(500) USING user_agent::varchar(500);
ALTER TABLE audit_logs
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS audit_org_result_created_idx
    ON audit_logs (organization_id, result, created_at);
"""

_AUDIT_LOG_XXZ_REVERSE = """
DROP INDEX IF EXISTS audit_org_result_created_idx;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS session_id;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS request_id;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS request_body;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS request_query;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS request_path;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS request_method;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS error_code;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS error_message;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS changes;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS details;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS user_name;
ALTER TABLE audit_logs DROP COLUMN IF EXISTS user_email;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0003_rename_audit_log_table"),
    ]

    state_operations = [
        migrations.AddField(
            model_name="auditlog",
            name="user_email",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="user_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="details",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="changes",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="result",
            field=models.CharField(
                choices=[
                    ("success", "Success"),
                    ("failure", "Failure"),
                    ("partial", "Partial"),
                ],
                db_index=True,
                default="success",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="error_message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="error_code",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="request_method",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="request_path",
            field=models.CharField(blank=True, default="", max_length=1000),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="request_query",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="request_body",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="request_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="session_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="created_at",
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="user_agent",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["organization", "result", "created_at"],
                name="audit_org_result_created_idx",
            ),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=_AUDIT_LOG_XXZ_FORWARD,
                    reverse_sql=_AUDIT_LOG_XXZ_REVERSE,
                ),
            ],
            state_operations=state_operations,
        ),
    ]
