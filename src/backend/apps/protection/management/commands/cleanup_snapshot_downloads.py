from django.core.management.base import BaseCommand

from apps.protection.services.snapshot_download import cleanup_expired_snapshot_download_artifacts


class Command(BaseCommand):
    help = "Expire snapshot download artifacts and remove their temporary files."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1000)

    def handle(self, *args, **options):
        count = cleanup_expired_snapshot_download_artifacts(limit=int(options["limit"]))
        self.stdout.write(self.style.SUCCESS(f"expired snapshot download artifacts: {count}"))
