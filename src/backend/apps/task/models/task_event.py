from django.db import models

from .task import Task
from .task_step import TaskStep


class TaskEvent(models.Model):
    class Level(models.TextChoices):
        INFO = "INFO", "Info"
        WARN = "WARN", "Warn"
        ERROR = "ERROR", "Error"
        DEBUG = "DEBUG", "Debug"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="events")
    step = models.ForeignKey(
        TaskStep,
        on_delete=models.SET_NULL,
        related_name="events",
        blank=True,
        null=True,
    )
    seq = models.BigIntegerField()
    level = models.CharField(max_length=16, choices=Level.choices, db_index=True)
    message = models.TextField()
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "task_event"
        ordering = ["seq", "id"]
        constraints = [
            models.UniqueConstraint(fields=["task", "seq"], name="uniq_task_event_seq"),
        ]
        indexes = [
            models.Index(fields=["task", "created_at"], name="task_event_task_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.task_id}:{self.seq}:{self.level}"
