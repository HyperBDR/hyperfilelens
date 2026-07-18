"""
Django signals for automatic user setup.
"""

import logging

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.utils import timezone

from apps.iam.profile_models import Profile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_resources(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        with transaction.atomic():
            Profile.objects.get_or_create(
                user=instance,
                defaults={
                    "registration_completed": False,
                    "language": "en",
                    "timezone": "UTC",
                    "registered_at": timezone.now(),
                },
            )
    except Exception as exc:
        logger.warning(
            "Failed to create profile for user %s: %s",
            instance.username,
            exc,
            exc_info=True,
        )
