"""Invalidate configuration cache when rows change."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.configuration.models import GlobalConfig
from apps.configuration.selectors.internal.cache import invalidate_entry


@receiver(post_save, sender=GlobalConfig)
@receiver(post_delete, sender=GlobalConfig)
def _clear_config_cache(sender, instance: GlobalConfig, **kwargs) -> None:
    invalidate_entry(
        config_key=instance.key,
        scope=instance.scope,
        tenant_key=instance.tenant_key or "",
    )
