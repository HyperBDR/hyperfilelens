# Thin iam_membership: drop role from Django state (authority → EE MemberRole /
# community default). Physical ``role`` column stays until ``0014`` (community)
# or EE ``membership.0001`` backfill + drop (enterprise), so backfill cannot race
# ahead of a hard DROP COLUMN.

from django.db import migrations, models


_STATE_OPS = [
    migrations.RemoveConstraint(
        model_name="membership",
        name="uniq_iam_org_active_owner",
    ),
    migrations.RemoveIndex(
        model_name="membership",
        name="iam_members_organiz_329c5d_idx",
    ),
    migrations.RemoveField(
        model_name="membership",
        name="role",
    ),
    migrations.AddIndex(
        model_name="membership",
        index=models.Index(
            fields=["organization", "is_active"],
            name="iam_members_org_active_idx",
        ),
    ),
    migrations.AddConstraint(
        model_name="membership",
        constraint=models.UniqueConstraint(
            fields=["user", "organization"],
            name="uniq_iam_user_org",
        ),
    ),
]

# Keep ``role`` column in DB until EE backfill / iam.0014 drops it.
# Make it nullable + DB default so Host ORM inserts (no role in state) succeed
# during the enterprise migrate window.
_DATABASE_OPS = [
    migrations.RemoveConstraint(
        model_name="membership",
        name="uniq_iam_org_active_owner",
    ),
    migrations.RemoveIndex(
        model_name="membership",
        name="iam_members_organiz_329c5d_idx",
    ),
    migrations.AddIndex(
        model_name="membership",
        index=models.Index(
            fields=["organization", "is_active"],
            name="iam_members_org_active_idx",
        ),
    ),
    migrations.AddConstraint(
        model_name="membership",
        constraint=models.UniqueConstraint(
            fields=["user", "organization"],
            name="uniq_iam_user_org",
        ),
    ),
    migrations.RunSQL(
        sql=(
            "ALTER TABLE iam_membership "
            "ALTER COLUMN role DROP NOT NULL, "
            "ALTER COLUMN role SET DEFAULT 'operator';"
        ),
        reverse_sql=(
            "ALTER TABLE iam_membership "
            "ALTER COLUMN role SET DEFAULT NULL, "
            "ALTER COLUMN role SET NOT NULL;"
        ),
    ),
]


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0012_email_verification_code_purpose"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=_STATE_OPS,
            database_operations=_DATABASE_OPS,
        ),
    ]
