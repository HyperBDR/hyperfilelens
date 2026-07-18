from decimal import Decimal
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Task",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("organization_id", models.BigIntegerField(db_index=True)),
                (
                    "task_type",
                    models.CharField(
                        choices=[("backup", "Backup"), ("restore", "Restore")],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("display_name", models.CharField(db_index=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                            ("timeout", "Timeout"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("progress", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("current_step", models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                ("retry_count", models.IntegerField(default=0)),
                (
                    "trigger_type",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("system", "System"),
                            ("retry", "Retry"),
                            ("api", "API"),
                            ("hook", "Hook"),
                        ],
                        db_index=True,
                        default="manual",
                        max_length=16,
                    ),
                ),
                ("request_payload", models.JSONField(blank=True, null=True)),
                ("result_payload", models.JSONField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "task",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="TaskResource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "resource_type",
                    models.CharField(
                        choices=[
                            ("backup_source", "Backup source"),
                            ("repository", "Repository"),
                            ("target_repository", "Target repository"),
                            ("snapshot", "Snapshot"),
                            ("host", "Host"),
                            ("volume", "Volume"),
                        ],
                        max_length=32,
                    ),
                ),
                ("resource_id", models.BigIntegerField()),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resources",
                        to="task.task",
                    ),
                ),
            ],
            options={
                "db_table": "task_resource",
            },
        ),
        migrations.CreateModel(
            name="TaskStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step_index", models.IntegerField()),
                ("step_name", models.CharField(db_index=True, max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("progress", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="task.task",
                    ),
                ),
            ],
            options={
                "db_table": "task_step",
                "ordering": ["step_index", "id"],
            },
        ),
        migrations.CreateModel(
            name="TaskEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seq", models.BigIntegerField()),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("INFO", "Info"),
                            ("WARN", "Warn"),
                            ("ERROR", "Error"),
                            ("DEBUG", "Debug"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("message", models.TextField()),
                ("metadata", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "step",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="task.taskstep",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="task.task",
                    ),
                ),
            ],
            options={
                "db_table": "task_event",
                "ordering": ["seq", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(fields=["organization_id", "status", "created_at"], name="task_org_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(fields=["organization_id", "task_type", "status"], name="task_org_type_status_idx"),
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(fields=["organization_id", "trigger_type", "created_at"], name="task_org_trigger_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="task",
            constraint=models.CheckConstraint(
                condition=models.Q(progress__gte=0) & models.Q(progress__lte=100),
                name="task_progress_range",
            ),
        ),
        migrations.AddIndex(
            model_name="taskresource",
            index=models.Index(fields=["resource_type", "resource_id"], name="task_resource_lookup_idx"),
        ),
        migrations.AddConstraint(
            model_name="taskresource",
            constraint=models.UniqueConstraint(
                fields=("task", "resource_type", "resource_id"),
                name="uniq_task_resource",
            ),
        ),
        migrations.AddIndex(
            model_name="taskstep",
            index=models.Index(fields=["task", "status"], name="task_step_task_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="taskstep",
            constraint=models.UniqueConstraint(fields=("task", "step_index"), name="uniq_task_step_index"),
        ),
        migrations.AddConstraint(
            model_name="taskstep",
            constraint=models.CheckConstraint(
                condition=models.Q(progress__gte=0) & models.Q(progress__lte=100),
                name="task_step_progress_range",
            ),
        ),
        migrations.AddIndex(
            model_name="taskevent",
            index=models.Index(fields=["task", "created_at"], name="task_event_task_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="taskevent",
            constraint=models.UniqueConstraint(fields=("task", "seq"), name="uniq_task_event_seq"),
        ),
    ]
