# Drop physical iam_membership.role after EE role backfill (when plugin present).

from django.apps import apps as django_apps
from django.db import migrations


def _ee_member_role_ready(schema_editor) -> bool:
    """True when enterprise role table exists (membership.0001 applied)."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(current_schema() || '.ee_member_role')"
        )
        row = cursor.fetchone()
        return bool(row and row[0])


def drop_role_column(apps, schema_editor):
    """Community: drop immediately. Enterprise: wait until ee_member_role exists.

    If the membership plugin is installed but has not migrated yet, leave the
    column so ``membership.0001`` can backfill; that migration drops the column.
    """
    membership_installed = django_apps.is_installed("membership")
    if membership_installed and not _ee_member_role_ready(schema_editor):
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE iam_membership DROP COLUMN IF EXISTS role"
        )


def noop_reverse(apps, schema_editor):
    # Role authority is EE-only; do not recreate Host role column on reverse.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0013_membership_thin_affiliation"),
    ]

    operations = [
        migrations.RunPython(drop_role_column, noop_reverse),
    ]
