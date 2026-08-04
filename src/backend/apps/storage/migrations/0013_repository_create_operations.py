from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0012_repository_s3_bucket_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="repositorytask",
            name="operation_type",
            field=models.CharField(
                choices=[
                    ("maintenance.quick", "Quick maintenance"),
                    ("maintenance.full", "Full maintenance"),
                    ("cleanup.target", "Delete subrepository"),
                    ("cleanup.repository", "Delete repository"),
                    ("check", "Check"),
                    ("create.repository", "Create repository"),
                    ("repair.bind", "Bind proxy"),
                    ("repair.remount", "Remount repository"),
                ],
                db_index=True,
                max_length=64,
            ),
        ),
    ]
