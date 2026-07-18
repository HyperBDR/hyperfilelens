from django.db import models

from .task import Task


class TaskResource(models.Model):
    class Type(models.TextChoices):
        BACKUP_SOURCE = "backup_source", "Backup source"
        BACKUP_CONFIG = "backup_config", "Backup config"
        REPOSITORY = "repository", "Repository"
        TARGET_REPOSITORY = "target_repository", "Target repository"
        SNAPSHOT = "snapshot", "Snapshot"
        HOST = "host", "Host"
        VOLUME = "volume", "Volume"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="resources")
    resource_type = models.CharField(max_length=32, choices=Type.choices)
    resource_subtype = models.CharField(max_length=32, blank=True, default="")
    resource_id = models.BigIntegerField()
    is_primary = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "task_resource"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "resource_type", "resource_subtype", "resource_id"],
                name="uniq_task_resource_subtype",
            ),
            models.UniqueConstraint(
                fields=["task"],
                condition=models.Q(is_primary=True),
                name="uniq_task_primary_resource",
            ),
        ]
        indexes = [
            models.Index(
                fields=["resource_type", "resource_subtype", "resource_id"],
                name="task_resource_lookup_idx",
            ),
        ]

    def __str__(self) -> str:
        subtype = f":{self.resource_subtype}" if self.resource_subtype else ""
        return f"{self.task_id}:{self.resource_type}{subtype}:{self.resource_id}"
