# Host-era ledger tables stay physical and unused (see EE legacy-ledger policy),
# but their FKs to iam_organization break TransactionTestCase flush: Django's
# sqlflush no longer knows about the detached models, so TRUNCATE iam_organization
# fails. Drop only foreign keys; keep tables and rows for Enterprise copy.

from django.db import migrations

_LEDGER_TABLES = (
    "subscription_org",
    "subscription_entitlement",
    "subscription_quota",
    "subscription_usage",
)


def drop_detached_ledger_foreign_keys(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for table in _LEDGER_TABLES:
            cursor.execute(
                """
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class rel ON rel.oid = c.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE c.contype = 'f'
                  AND rel.relname = %s
                  AND nsp.nspname = current_schema()
                """,
                [table],
            )
            for (conname,) in cursor.fetchall():
                cursor.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{conname}"')


class Migration(migrations.Migration):
    dependencies = [
        ("subscription", "0004_detach_ledger_models"),
    ]

    operations = [
        migrations.RunPython(
            drop_detached_ledger_foreign_keys,
            migrations.RunPython.noop,
        ),
    ]
