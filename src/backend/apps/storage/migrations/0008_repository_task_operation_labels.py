from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0007_repository_cleanup"),
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
                ],
                db_index=True,
                max_length=64,
            ),
        ),
    ]
