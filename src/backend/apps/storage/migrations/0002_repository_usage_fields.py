from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="repository",
            old_name="used_bytes",
            new_name="estimated_usage_bytes",
        ),
        migrations.AddField(
            model_name="repository",
            name="physical_usage_bytes",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
