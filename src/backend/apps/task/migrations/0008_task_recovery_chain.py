from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("task", "0007_task_resource_primary")]

    operations = [
        migrations.AddField(
            model_name="task",
            name="recovery_attempt",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="task",
            name="replaces_task",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replacement_task",
                to="task.task",
            ),
        ),
    ]
