"""
Align pre-refactor node tables with current model db_table names.

Older databases created ``node_node``, ``node_enrollment_token``, and
``node_agent_task_delivery`` while ``0001_initial`` is recorded as applied
with the new names (``node_nodes``, ``node_tokens``, ``node_tasks``).
"""

from django.db import migrations


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        [table_name],
    )
    return bool(cursor.fetchone()[0])


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
        )
        """,
        [table_name, column_name],
    )
    return bool(cursor.fetchone()[0])


def align_legacy_node_tables(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if _table_exists(cursor, "node_node") and not _table_exists(cursor, "node_nodes"):
            cursor.execute('ALTER TABLE "node_node" RENAME TO "node_nodes"')
            if _column_exists(cursor, "node_nodes", "capabilities"):
                cursor.execute(
                    'ALTER TABLE "node_nodes" RENAME COLUMN "capabilities" TO "metadata"'
                )
            if not _column_exists(cursor, "node_nodes", "is_deleted"):
                cursor.execute(
                    'ALTER TABLE "node_nodes" '
                    'ADD COLUMN "is_deleted" boolean NOT NULL DEFAULT false'
                )
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS "node_nodes_is_deleted_idx" '
                    'ON "node_nodes" ("is_deleted")'
                )
            if not _column_exists(cursor, "node_nodes", "deleted_at"):
                cursor.execute(
                    'ALTER TABLE "node_nodes" '
                    'ADD COLUMN "deleted_at" timestamp with time zone NULL'
                )
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS "node_nodes_deleted_at_idx" '
                    'ON "node_nodes" ("deleted_at")'
                )

        if _table_exists(cursor, "node_enrollment_token") and not _table_exists(
            cursor, "node_tokens"
        ):
            cursor.execute(
                'ALTER TABLE "node_enrollment_token" RENAME TO "node_tokens"'
            )
            if not _column_exists(cursor, "node_tokens", "updated_at"):
                cursor.execute(
                    'ALTER TABLE "node_tokens" '
                    'ADD COLUMN "updated_at" timestamp with time zone NOT NULL DEFAULT NOW()'
                )
            if not _column_exists(cursor, "node_tokens", "is_deleted"):
                cursor.execute(
                    'ALTER TABLE "node_tokens" '
                    'ADD COLUMN "is_deleted" boolean NOT NULL DEFAULT false'
                )
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS "node_tokens_is_deleted_idx" '
                    'ON "node_tokens" ("is_deleted")'
                )
            if not _column_exists(cursor, "node_tokens", "deleted_at"):
                cursor.execute(
                    'ALTER TABLE "node_tokens" '
                    'ADD COLUMN "deleted_at" timestamp with time zone NULL'
                )
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS "node_tokens_deleted_at_idx" '
                    'ON "node_tokens" ("deleted_at")'
                )

        if _table_exists(cursor, "node_agent_task_delivery") and not _table_exists(
            cursor, "node_tasks"
        ):
            cursor.execute(
                'ALTER TABLE "node_agent_task_delivery" RENAME TO "node_tasks"'
            )
            if _column_exists(cursor, "node_tasks", "deadline_at"):
                cursor.execute(
                    'ALTER TABLE "node_tasks" '
                    'RENAME COLUMN "deadline_at" TO "watchdog_deadline_at"'
                )
            if _column_exists(cursor, "node_tasks", "acked_at"):
                cursor.execute(
                    'ALTER TABLE "node_tasks" '
                    'RENAME COLUMN "acked_at" TO "last_progress_at"'
                )
            if not _column_exists(cursor, "node_tasks", "result"):
                cursor.execute(
                    'ALTER TABLE "node_tasks" '
                    'ADD COLUMN "result" jsonb NOT NULL DEFAULT \'{}\'::jsonb'
                )
            if not _column_exists(cursor, "node_tasks", "is_deleted"):
                cursor.execute(
                    'ALTER TABLE "node_tasks" '
                    'ADD COLUMN "is_deleted" boolean NOT NULL DEFAULT false'
                )
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS "node_tasks_is_deleted_idx" '
                    'ON "node_tasks" ("is_deleted")'
                )
            if not _column_exists(cursor, "node_tasks", "deleted_at"):
                cursor.execute(
                    'ALTER TABLE "node_tasks" '
                    'ADD COLUMN "deleted_at" timestamp with time zone NULL'
                )
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS "node_tasks_deleted_at_idx" '
                    'ON "node_tasks" ("deleted_at")'
                )


def reverse_align_legacy_node_tables(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if _table_exists(cursor, "node_nodes") and not _table_exists(cursor, "node_node"):
            if _column_exists(cursor, "node_nodes", "metadata"):
                cursor.execute(
                    'ALTER TABLE "node_nodes" RENAME COLUMN "metadata" TO "capabilities"'
                )
            cursor.execute('ALTER TABLE "node_nodes" RENAME TO "node_node"')

        if _table_exists(cursor, "node_tokens") and not _table_exists(
            cursor, "node_enrollment_token"
        ):
            cursor.execute(
                'ALTER TABLE "node_tokens" RENAME TO "node_enrollment_token"'
            )

        if _table_exists(cursor, "node_tasks") and not _table_exists(
            cursor, "node_agent_task_delivery"
        ):
            if _column_exists(cursor, "node_tasks", "watchdog_deadline_at"):
                cursor.execute(
                    'ALTER TABLE "node_tasks" '
                    'RENAME COLUMN "watchdog_deadline_at" TO "deadline_at"'
                )
            if _column_exists(cursor, "node_tasks", "last_progress_at"):
                cursor.execute(
                    'ALTER TABLE "node_tasks" '
                    'RENAME COLUMN "last_progress_at" TO "acked_at"'
                )
            cursor.execute(
                'ALTER TABLE "node_tasks" RENAME TO "node_agent_task_delivery"'
            )


class Migration(migrations.Migration):
    dependencies = [
        ("node", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            align_legacy_node_tables,
            reverse_align_legacy_node_tables,
        ),
    ]
