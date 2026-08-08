# Detach Plan/OrgSubscription/Entitlement/Quota/UsageCounter from Host state.
# Physical tables remain unused. Commercial plugin copies needed rows into
# ee_* tables (currently ee_quota only); it does not re-bind all five models.
# Follow-up 0005 drops their FKs so Community TransactionTestCase flush works.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("subscription", "0003_alter_license_change_type_alter_license_status"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="OrganizationSubscription"),
                migrations.DeleteModel(name="Entitlement"),
                migrations.DeleteModel(name="Quota"),
                migrations.DeleteModel(name="UsageCounter"),
                migrations.DeleteModel(name="Plan"),
            ],
            database_operations=[],
        ),
    ]
