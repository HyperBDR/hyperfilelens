from decimal import Decimal

from django.db import models

from .task import Task


class TaskStep(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="steps")
    step_index = models.IntegerField()
    step_name = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "task_step"
        ordering = ["step_index", "id"]
        constraints = [
            models.UniqueConstraint(fields=["task", "step_index"], name="uniq_task_step_index"),
            models.CheckConstraint(
                check=models.Q(progress__gte=0) & models.Q(progress__lte=100),
                name="task_step_progress_range",
            ),
        ]
        indexes = [
            models.Index(fields=["task", "status"], name="task_step_task_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.task_id}:{self.step_index}:{self.step_name}"
