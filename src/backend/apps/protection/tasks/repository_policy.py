from celery import shared_task

from apps.protection.services.repository_policy import sync_backup_config_repository_policy


@shared_task(name="apps.protection.tasks.repository_policy.sync_backup_config_repository_policy")
def sync_backup_config_repository_policy_task(*, config_id: int) -> dict:
    return sync_backup_config_repository_policy(config_id=int(config_id))
