"""
Storage app config.
"""

from django.apps import AppConfig


class StorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.storage"
    verbose_name = "Storage"

    def ready(self) -> None:
        # Fail fast on invalid maintenance intervals, windows, timezone, or concurrency.
        from apps.storage.services.internal.repository_operations import maintenance_settings

        maintenance_settings()
