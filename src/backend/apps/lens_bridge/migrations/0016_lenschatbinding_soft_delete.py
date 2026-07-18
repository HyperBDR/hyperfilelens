from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0015_session_chat_configuration"),
    ]

    operations = [
        migrations.AddField(
            model_name="lenschatbinding",
            name="deleted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lenschatbinding",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
