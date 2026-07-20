"""
Storage app config.
"""

from django.apps import AppConfig


class StorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.storage"
    verbose_name = "Storage"

    def ready(self) -> None:
        # Fail fast on invalid storage task configuration.
        from apps.storage.conf import repository_health_interval_seconds
        from apps.storage.services.internal.repository_operations import (
            maintenance_settings,
        )

        maintenance_settings()
        repository_health_interval_seconds()
