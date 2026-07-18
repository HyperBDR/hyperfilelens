from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0004_session_agent_model_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensorgmodellink",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
    ]
