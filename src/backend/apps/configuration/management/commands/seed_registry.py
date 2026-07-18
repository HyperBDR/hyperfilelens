"""Seed global rows for all registered configuration keys (idempotent)."""

from django.core.management.base import BaseCommand

from apps.configuration.models import GlobalConfig
from apps.configuration.services.internal.registry import all_key_specs
from apps.storage import conf as storage_conf
from apps.storage.config import seed_global_config


class Command(BaseCommand):
    help = "Seed GlobalConfig rows for registry keys that have code defaults"

    def handle(self, *args, **options):
        seed_global_config()

        specs = all_key_specs()
        created = 0
        for spec in specs:
            if spec.key in (
                storage_conf.CONFIG_KEY_RETENTION,
                storage_conf.CONFIG_KEY_FILTERS,
            ):
                continue
            _row, was_created = GlobalConfig.objects.get_or_create(
                key=spec.key,
                scope=GlobalConfig.Scope.GLOBAL,
                tenant_key="",
                defaults={
                    "value": _placeholder_for_spec(spec),
                    "value_type": spec.value_type,
                    "category": spec.category,
                    "description": spec.description,
                    "is_active": False,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Registry seed complete (storage templates + {created} placeholder rows)",
            ),
        )


def _placeholder_for_spec(spec) -> object:
    if spec.value_type == GlobalConfig.ValueType.BOOLEAN:
        return False
    if spec.value_type == GlobalConfig.ValueType.NUMBER:
        return 0
    if spec.value_type == GlobalConfig.ValueType.ARRAY:
        return []
    if spec.value_type == GlobalConfig.ValueType.OBJECT:
        return {}
    return ""
