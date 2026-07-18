"""
Alert app.
"""

from django.apps import AppConfig


class AlertConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.alert"
    label = "alerts"
    verbose_name = "Alerts"

    def ready(self) -> None:
        import apps.alert.signals  # noqa: F401

