from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lens_bridge", "0010_lensorgmcplink_lensorgskilllink"),
    ]

    operations = [
        migrations.AddField(
            model_name="lenssessionlink",
            name="active_run_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="active_run_status",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
