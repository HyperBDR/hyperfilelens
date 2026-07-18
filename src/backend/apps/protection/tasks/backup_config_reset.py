from __future__ import annotations

import logging

from celery import shared_task

from common.observability.celery_context import celery_trace

from apps.protection.services.backup_config_reset import run_backup_config_reset_task

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.protection.tasks.backup_config_reset.execute_backup_config_reset_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def execute_backup_config_reset_task(
    self,
    *,
    organization_id: int,
    task_uuid: str,
    source_type: str,
    source_ref_id: int,
) -> dict:
    trace_id = str(task_uuid or getattr(self.request, "id", "") or "")
    with celery_trace(trace_id, task_name="apps.protection.tasks.backup_config_reset.execute_backup_config_reset_task"):
        logger.info(
            "celery task started name=apps.protection.tasks.backup_config_reset.execute_backup_config_reset_task "
            "task_uuid=%s org_id=%s source=%s:%s",
            task_uuid,
            organization_id,
            source_type,
            source_ref_id,
        )
        return run_backup_config_reset_task(
            organization_id=int(organization_id),
            task_uuid=str(task_uuid),
            source_type=str(source_type),
            source_ref_id=int(source_ref_id),
        )


@shared_task(
    name="apps.protection.tasks.backup_config_reset.reconcile_stuck_backup_config_reset_tasks_task",
    bind=True,
)
def reconcile_stuck_backup_config_reset_tasks_task(self, *, limit: int = 50) -> dict[str, int]:
    from apps.protection.services.backup_config_reset import reconcile_stuck_backup_config_reset_tasks

    summary = reconcile_stuck_backup_config_reset_tasks(limit=int(limit))
    if summary.get("redispatched"):
        logger.info("reconcile_stuck_backup_config_reset_tasks complete %s", summary)
    return summary
