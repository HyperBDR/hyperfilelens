from django.apps import AppConfig


class RestoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.restore"
    label = "restore"
    verbose_name = "Restore"

    def ready(self) -> None:
        import apps.restore.signals  # noqa: F401
