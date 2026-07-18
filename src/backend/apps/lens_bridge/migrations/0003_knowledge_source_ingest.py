from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0002_org_model_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensknowledgesource",
            name="backup_snapshot_directory_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="ingest_policy_json",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
