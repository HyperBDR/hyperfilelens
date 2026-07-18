from django.apps import AppConfig


class ProtectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.protection"
    verbose_name = "Protection"

    def ready(self) -> None:
        import apps.protection.tasks  # noqa: F401
