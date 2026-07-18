from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("task", "0006_repository_operation_task_type")]

    operations = [
        migrations.AddField(
            model_name="taskresource",
            name="is_primary",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddConstraint(
            model_name="taskresource",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_primary=True),
                fields=("task",),
                name="uniq_task_primary_resource",
            ),
        ),
    ]
