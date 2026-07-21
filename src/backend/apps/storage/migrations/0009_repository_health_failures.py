from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0008_repository_task_operation_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="health_failures",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
