from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0018_lensusageledger"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensorgmodellink",
            name="management_key",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64
            ),
        ),
        migrations.AddConstraint(
            model_name="lensorgmodellink",
            constraint=models.UniqueConstraint(
                condition=~models.Q(management_key=""),
                fields=("organization", "management_key"),
                name="uniq_lens_borgmdl_org_mgmt_key",
            ),
        ),
    ]
