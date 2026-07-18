"""Task app config."""

from django.apps import AppConfig


class TaskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.task"
    label = "task"
    verbose_name = "Task"

    def ready(self) -> None:
        import apps.task.signals  # noqa: F401
