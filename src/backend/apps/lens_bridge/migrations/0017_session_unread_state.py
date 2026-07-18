from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0016_lenschatbinding_soft_delete"),
    ]

    operations = [
        migrations.AddField(
            model_name="lenssessionlink",
            name="last_assistant_message_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="last_viewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
