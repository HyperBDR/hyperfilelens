from django.apps import AppConfig


class SourceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.source"
    label = "source"
    verbose_name = "Source Resources"

    def ready(self) -> None:
        import apps.source.tasks  # noqa: F401
