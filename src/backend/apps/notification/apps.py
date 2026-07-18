from django.apps import AppConfig


class NotificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notification"
    label = "notification"
    verbose_name = "Notification"

    def ready(self) -> None:
        import apps.notification.signals  # noqa: F401
