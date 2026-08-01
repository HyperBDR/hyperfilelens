from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0025_gateway_provision_and_assistant_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="lenssluserlink",
            name="sl_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
    ]
