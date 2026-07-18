"""Purge audit logs older than N days."""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "Delete audit logs older than --days (default 365)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365)

    def handle(self, *args, **options):
        days = int(options["days"])
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} audit log rows (>{days}d)."))
