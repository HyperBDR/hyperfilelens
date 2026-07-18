"""Seed storage-related GlobalConfig rows."""

from django.core.management.base import BaseCommand

from apps.storage.config import seed_global_config


class Command(BaseCommand):
    help = "Seed global backup/storage configuration templates"

    def handle(self, *args, **options):
        seed_global_config()
        self.stdout.write(self.style.SUCCESS("Storage configuration templates seeded."))
