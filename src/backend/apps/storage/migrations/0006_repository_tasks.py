from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0005_repository_usage_shard_mount_point"),
        ("task", "0006_repository_operation_task_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="RepositoryExecutionTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("target_key", models.CharField(max_length=700, unique=True)),
                ("owner_type", models.CharField(choices=[("controller", "Controller"), ("node", "Node")], max_length=20)),
                ("owner_node_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("owner_identity", models.CharField(max_length=255)),
                ("repository_subdir", models.CharField(blank=True, default="", max_length=500)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("active_task", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="locked_repository_target", to="task.task")),
                ("repository", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="execution_targets", to="storage.repository")),
            ],
            options={"db_table": "storage_repository_execution_target", "ordering": ["organization_id", "repository_id", "target_key"]},
        ),
        migrations.CreateModel(
            name="RepositoryMaintenanceState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_quick_success_at", models.DateTimeField(blank=True, null=True)),
                ("next_quick_due_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_full_success_at", models.DateTimeField(blank=True, null=True)),
                ("next_full_due_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_failure_at", models.DateTimeField(blank=True, null=True)),
                ("consecutive_failures", models.PositiveIntegerField(default=0)),
                ("next_retry_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("execution_target", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="maintenance_state", to="storage.repositoryexecutiontarget")),
            ],
            options={"db_table": "storage_repository_maintenance_state"},
        ),
        migrations.CreateModel(
            name="RepositoryTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_type", models.CharField(choices=[("maintenance.quick", "Quick maintenance"), ("maintenance.full", "Full maintenance"), ("cleanup", "Cleanup"), ("check", "Check")], db_index=True, max_length=64)),
                ("owner_type", models.CharField(choices=[("controller", "Controller"), ("node", "Node")], max_length=20)),
                ("owner_node_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("owner_identity", models.CharField(max_length=255)),
                ("due_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("remote_task_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("execution_target", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="repository_tasks", to="storage.repositoryexecutiontarget")),
                ("repository", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="repository_tasks", to="storage.repository")),
                ("task", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="repository_operation", to="task.task")),
            ],
            options={"db_table": "storage_repository_task", "ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(model_name="repositoryexecutiontarget", index=models.Index(fields=["organization_id", "repository", "is_active"], name="stor_ret_org_repo_act_idx")),
        migrations.AddIndex(model_name="repositoryexecutiontarget", index=models.Index(fields=["owner_type", "owner_node_id", "is_active"], name="storage_ret_owner_active_idx")),
        migrations.AddIndex(model_name="repositorytask", index=models.Index(fields=["repository", "operation_type", "created_at"], name="stor_rt_repo_op_cr_idx")),
        migrations.AddIndex(model_name="repositorytask", index=models.Index(fields=["execution_target", "operation_type", "created_at"], name="stor_rt_tgt_op_cr_idx")),
    ]
