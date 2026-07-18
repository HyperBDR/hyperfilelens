from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0004_remove_snapshot_capacity_delta_fields"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="backupconfig",
            name="uniq_prot_bcfg_org_name",
        ),
    ]