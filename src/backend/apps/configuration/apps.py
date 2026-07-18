"""
App configuration for runtime configuration center (platform layer).
"""

from django.apps import AppConfig


class ConfigurationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.configuration"
    label = "app_config"
    verbose_name = "Configuration"

    def ready(self) -> None:
        from apps.configuration import signals  # noqa: F401
