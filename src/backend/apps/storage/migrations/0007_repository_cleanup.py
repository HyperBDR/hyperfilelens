import django.db.models.deletion

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0006_repository_tasks"),
        ("task", "0007_task_resource_primary"),
    ]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="cleanup_result",
            field=models.CharField(
                blank=True,
                choices=[
                    ("deleted", "Physical repository deleted"),
                    ("force_skipped", "Physical repository retained"),
                ],
                db_index=True,
                default="",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="repository",
            name="removed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="repositorytask",
            name="execution_target",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="repository_tasks",
                to="storage.repositoryexecutiontarget",
            ),
        ),
        migrations.AlterField(
            model_name="repositorytask",
            name="operation_type",
            field=models.CharField(
                choices=[
                    ("maintenance.quick", "Quick maintenance"),
                    ("maintenance.full", "Full maintenance"),
                    ("cleanup.target", "Physical target cleanup"),
                    ("cleanup.repository", "Repository lifecycle cleanup"),
                    ("check", "Check"),
                ],
                db_index=True,
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="repositorytask",
            name="force",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="repositorytask",
            name="requested_by_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="repositorytask",
            name="triggered_by_task",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="triggered_repository_operations",
                to="task.task",
            ),
        ),
        migrations.AddIndex(
            model_name="repositorytask",
            index=models.Index(
                fields=["triggered_by_task", "operation_type", "created_at"],
                name="stor_rt_trigger_op_cr_idx",
            ),
        ),
    ]
