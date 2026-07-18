from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0005_org_model_display_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensknowledgesource",
            name="source_scopes_json",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
