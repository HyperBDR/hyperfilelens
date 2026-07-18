from __future__ import annotations

import logging

from celery import shared_task

from common.observability.celery_context import celery_trace

from apps.protection.services.snapshot_delete import reconcile_snapshot_delete_tasks, run_snapshot_delete_task

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.protection.tasks.snapshot_delete.execute_snapshot_delete_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def execute_snapshot_delete_task(
    self,
    *,
    organization_id: int,
    task_uuid: str,
    source_snapshot_id: int,
) -> dict:
    trace_id = str(task_uuid or getattr(self.request, "id", "") or "")
    with celery_trace(trace_id, task_name="apps.protection.tasks.snapshot_delete.execute_snapshot_delete_task"):
        logger.info(
            "celery task started name=apps.protection.tasks.snapshot_delete.execute_snapshot_delete_task "
            "task_uuid=%s org_id=%s source_snapshot_id=%s",
            task_uuid,
            organization_id,
            source_snapshot_id,
        )
        return run_snapshot_delete_task(
            organization_id=int(organization_id),
            task_uuid=str(task_uuid),
            source_snapshot_id=int(source_snapshot_id),
        )


@shared_task(name="apps.protection.tasks.snapshot_delete.reconcile_snapshot_delete_tasks")
def reconcile_snapshot_delete_tasks_task(*, limit: int = 100) -> dict[str, int]:
    return reconcile_snapshot_delete_tasks(limit=int(limit))
