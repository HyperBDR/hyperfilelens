from __future__ import annotations

import logging

from celery import shared_task

from apps.protection.services.policy_execution import run_backup_policy_maintenance

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.protection.tasks.policy_execution.run_backup_policy_maintenance",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def run_backup_policy_maintenance_task(self, *, retention_limit: int = 100) -> dict[str, int]:
    summary = run_backup_policy_maintenance(retention_limit=int(retention_limit))
    logger.debug("run_backup_policy_maintenance complete %s", summary)
    return summary
