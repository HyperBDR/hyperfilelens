from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0011_unique_backup_config_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="backupconfig",
            name="compression_level",
            field=models.CharField(
                choices=[("none", "None"), ("balanced", "Balanced"), ("high", "High")],
                default="balanced",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="backupconfig",
            constraint=models.CheckConstraint(
                condition=models.Q(compression_level__in=["none", "balanced", "high"]),
                name="prot_bcfg_compression_valid",
            ),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshot",
            name="policy_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RemoveField(
            model_name="filefilterrule",
            name="add_dot_ignore_enabled",
        ),
        migrations.RemoveField(
            model_name="filefilterrule",
            name="dot_ignore_filenames",
        ),
        migrations.RemoveField(
            model_name="filefilterrule",
            name="error_handling",
        ),
    ]
