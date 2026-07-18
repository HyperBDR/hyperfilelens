from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from common.observability.celery_context import celery_trace

logger = logging.getLogger(__name__)

_SOFT_LIMIT = int(getattr(settings, "LENS_KS_SYNC_SOFT_TIME_LIMIT", 3600))
_TIME_LIMIT = int(getattr(settings, "LENS_KS_SYNC_TIME_LIMIT", 7200))


@shared_task(
    name="apps.lens_bridge.tasks.knowledge_source_sync.execute_knowledge_source_sync_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
    soft_time_limit=_SOFT_LIMIT,
    time_limit=_TIME_LIMIT,
)
def execute_knowledge_source_sync_task(
    self,
    *,
    organization_id: int,
    knowledge_source_id: int,
    mode: str = "resume",
) -> dict:
    trace_id = f"ks-sync-{knowledge_source_id}"
    with celery_trace(trace_id, task_name="apps.lens_bridge.tasks.knowledge_source_sync.execute_knowledge_source_sync_task"):
        from apps.lens_bridge.services.knowledge_source_sync import run_knowledge_source_sync

        logger.info(
            "knowledge source sync celery started ks_id=%s org_id=%s mode=%s",
            knowledge_source_id,
            organization_id,
            mode,
        )
        result = run_knowledge_source_sync(
            organization_id=int(organization_id),
            knowledge_source_id=int(knowledge_source_id),
        )
        logger.info(
            "knowledge source sync celery finished ks_id=%s status=%s",
            knowledge_source_id,
            result.get("status"),
        )
        return result
