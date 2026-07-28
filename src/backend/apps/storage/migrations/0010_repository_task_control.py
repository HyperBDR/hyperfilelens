from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("storage", "0009_repository_health_failures")]

    operations = [
        migrations.AddField(
            model_name="repositorytask",
            name="cancel_reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="repositorytask",
            name="cancel_requested_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="repositorytask",
            name="execution_heartbeat_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="repositorytask",
            name="execution_token",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
