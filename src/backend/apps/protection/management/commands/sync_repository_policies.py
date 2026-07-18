from django.core.management.base import BaseCommand

from apps.protection.models import BackupConfig
from apps.protection.tasks.repository_policy import sync_backup_config_repository_policy_task


class Command(BaseCommand):
    help = "Queue Kopia policy synchronization for active backup configurations."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Queue tasks; default is dry-run.")
        parser.add_argument("--organization-id", type=int)
        parser.add_argument("--config-id", type=int)

    def handle(self, *args, **options):
        configs = BackupConfig.objects.filter(status=BackupConfig.Status.ACTIVE).order_by("id")
        if options.get("organization_id") is not None:
            configs = configs.filter(organization_id=options["organization_id"])
        if options.get("config_id") is not None:
            configs = configs.filter(id=options["config_id"])
        config_ids = list(configs.values_list("id", flat=True))
        for config_id in config_ids:
            self.stdout.write(f"backup_config={config_id} action={'queue' if options['apply'] else 'would-queue'}")
            if options["apply"]:
                sync_backup_config_repository_policy_task.delay(config_id=config_id)
        mode = "APPLY" if options["apply"] else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(f"{mode}: configurations={len(config_ids)}"))
