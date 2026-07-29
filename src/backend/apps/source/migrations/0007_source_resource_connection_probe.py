from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("source", "0006_source_resource_removal_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourceresource",
            name="connection_probe_token",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="sourceresource",
            name="connection_test_status",
            field=models.CharField(
                choices=[
                    ("idle", "Idle"),
                    ("pending", "Pending"),
                    ("running", "Running"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="idle",
                max_length=20,
            ),
        ),
    ]
