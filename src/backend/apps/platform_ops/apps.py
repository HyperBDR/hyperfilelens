"""Thin OSS Platform Ops: models/migrations. Console APIs come from EE via extend_path."""

from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PlatformOpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform_ops"
    verbose_name = "Platform Ops"

    def ready(self) -> None:
        try:
            from common.admin_autoregister import autoregister_project_models

            count = autoregister_project_models()
            if count:
                logger.info("Django Admin: auto-registered %s project model(s)", count)
        except Exception:
            logger.exception("Failed to auto-register Django Admin models")

        # When EE is on sys.path, register its audit writer.
        try:
            from apps.platform_ops.services.internal.audit import write_platform_audit_log
            from common.platform_audit import register_platform_audit_writer

            register_platform_audit_writer(write_platform_audit_log)
        except ImportError:
            pass
        except Exception:
            logger.exception("Failed to register platform audit writer")
