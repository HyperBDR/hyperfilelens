import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PlatformOpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform_ops"
    verbose_name = "Platform Ops"

    def ready(self) -> None:
        # Run after django.contrib.admin autodiscover and per-app admin.py modules.
        try:
            from common.admin_autoregister import autoregister_project_models

            count = autoregister_project_models()
            if count:
                logger.info("Django Admin: auto-registered %s project model(s)", count)
        except Exception:
            logger.exception("Failed to auto-register Django Admin models")
