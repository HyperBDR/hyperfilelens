from __future__ import annotations

import logging

from celery import shared_task

from common.observability.celery_context import celery_trace

logger = logging.getLogger(__name__)


def queue_source_unregister_task(*, task_id: int) -> None:
    from apps.source.tasks.source_unregister import execute_source_unregister_task

    execute_source_unregister_task.delay(task_id=int(task_id))


@shared_task(
    name="apps.source.tasks.source_unregister.execute_source_unregister_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def execute_source_unregister_task(self, *, task_id: int) -> dict:
    from apps.source.services.internal.backup_source_delete import run_source_unregister_task
    from apps.task.models import Task

    task = Task.objects.filter(pk=int(task_id)).first()
    if task is None:
        raise Task.DoesNotExist(f"source unregister task id={task_id} not found")
    trace_id = str(task.task_uuid or getattr(self.request, "id", "") or "")
    with celery_trace(trace_id, task_name="apps.source.tasks.source_unregister.execute_source_unregister_task"):
        logger.info(
            "celery task started name=apps.source.tasks.source_unregister.execute_source_unregister_task "
            "task_id=%s task_uuid=%s org_id=%s",
            task_id,
            task.task_uuid,
            task.organization_id,
        )
        return run_source_unregister_task(
            organization_id=int(task.organization_id),
            task_uuid=str(task.task_uuid),
        )


@shared_task(
    name="apps.source.tasks.source_unregister.reconcile_stuck_source_unregister_tasks_task",
    bind=True,
)
def reconcile_stuck_source_unregister_tasks_task(self, *, limit: int = 50) -> dict[str, int]:
    from apps.source.services.internal.backup_source_delete import reconcile_stuck_source_unregister_tasks

    summary = reconcile_stuck_source_unregister_tasks(limit=int(limit))
    if summary.get("redispatched"):
        logger.info("reconcile_stuck_source_unregister_tasks complete %s", summary)
    return summary
