from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("storage", "0013_repository_create_operations")]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="metrics_last_attempt_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="repository",
            name="usage_probe_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(model_name="repository", name="usage_last_success_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="repository", name="usage_last_error", field=models.CharField(blank=True, default="", max_length=1000)),
        migrations.AddField(
            model_name="repository",
            name="capacity_probe_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(model_name="repository", name="capacity_last_success_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="repository", name="capacity_last_error", field=models.CharField(blank=True, default="", max_length=1000)),
    ]
