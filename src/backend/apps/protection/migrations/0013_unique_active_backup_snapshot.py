from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0012_compression_runtime_policy"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="backupsourcesnapshot",
            constraint=models.UniqueConstraint(
                fields=("organization_id", "backup_config_id"),
                condition=models.Q(status="creating"),
                name="uniq_prot_bsrcsnap_active_cfg",
            ),
        ),
    ]
