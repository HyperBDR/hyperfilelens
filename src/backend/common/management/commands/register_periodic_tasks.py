"""
Discover installed apps' periodic_tasks and register them to Celery Beat.
"""

import importlib
import logging

from django.apps import apps
from django.core.management.base import BaseCommand

from common.scheduling.registry import TASK_REGISTRY, apply_registry


logger = logging.getLogger(__name__)


def discover_and_register() -> None:
    TASK_REGISTRY.clear()

    for app_config in apps.get_app_configs():
        if not app_config.name.startswith("apps."):
            continue
        module_name = f"{app_config.name}.periodic_tasks"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue

        register = getattr(module, "register_periodic_tasks", None)
        if register is None:
            continue

        try:
            register()
        except Exception as exc:
            logger.exception(
                "register_periodic_tasks failed for %s: %s", app_config.name, exc
            )

    apply_registry()


class Command(BaseCommand):
    help = (
        "Discover apps' periodic_tasks.register_periodic_tasks() and register "
        "entries to django_celery_beat without updating existing rows."
    )

    def handle(self, *args, **options):
        discover_and_register()
        count = len(TASK_REGISTRY)
        self.stdout.write(
            self.style.SUCCESS(
                f"Registered {count} periodic task(s) to django_celery_beat."
            )
        )
