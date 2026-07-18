from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from common.observability.celery_context import celery_trace

from apps.protection.services.backup_orchestrator import reconcile_backup_tasks
from apps.protection.services.backup_task import (
    reconcile_interrupted_backup_tasks,
    run_backup_task,
)

logger = logging.getLogger(__name__)

_BACKUP_ORCHESTRATION_SOFT_LIMIT = int(
    getattr(settings, "CELERY_BACKUP_TASK_SOFT_TIME_LIMIT", 30)
)
_BACKUP_ORCHESTRATION_TIME_LIMIT = int(
    getattr(settings, "CELERY_BACKUP_TASK_TIME_LIMIT", 60)
)


@shared_task(
    name="apps.protection.tasks.backup.execute_backup_source_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    soft_time_limit=_BACKUP_ORCHESTRATION_SOFT_LIMIT,
    time_limit=_BACKUP_ORCHESTRATION_TIME_LIMIT,
)
def execute_backup_source_task(
    self,
    *,
    organization_id: int,
    task_uuid: str,
    source_snapshot_id: int,
) -> dict:
    trace_id = str(task_uuid or getattr(self.request, "id", "") or "")
    with celery_trace(trace_id, task_name="apps.protection.tasks.backup.execute_backup_source_task"):
        logger.info(
            "celery task started name=apps.protection.tasks.backup.execute_backup_source_task "
            "task_uuid=%s org_id=%s source_snapshot_id=%s",
            task_uuid,
            organization_id,
            source_snapshot_id,
        )
        try:
            result = run_backup_task(
                organization_id=int(organization_id),
                task_uuid=str(task_uuid),
                source_snapshot_id=int(source_snapshot_id),
            )
        except Exception:
            logger.exception(
                "celery task failed name=apps.protection.tasks.backup.execute_backup_source_task "
                "task_uuid=%s org_id=%s source_snapshot_id=%s",
                task_uuid,
                organization_id,
                source_snapshot_id,
            )
            raise
        logger.info(
            "celery task finished name=apps.protection.tasks.backup.execute_backup_source_task "
            "task_uuid=%s status=%s",
            task_uuid,
            result.get("status") if isinstance(result, dict) else "-",
        )
        return result


@shared_task(
    name="apps.protection.tasks.backup.reconcile_backup_tasks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    soft_time_limit=120,
    time_limit=180,
)
def reconcile_backup_tasks_task(self, *, limit: int = 100) -> dict[str, int]:
    summary = reconcile_backup_tasks(limit=int(limit))
    logger.debug("reconcile_backup_tasks complete %s", summary)
    return summary


@shared_task(
    name="apps.protection.tasks.backup.reconcile_interrupted_backup_tasks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def reconcile_interrupted_backup_tasks_task(self, *, limit: int = 100) -> dict[str, int]:
    summary = reconcile_interrupted_backup_tasks(limit=int(limit))
    logger.debug("reconcile_interrupted_backup_tasks complete %s", summary)
    return summary
