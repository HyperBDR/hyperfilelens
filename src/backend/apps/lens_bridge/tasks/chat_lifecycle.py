from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from common.observability.celery_context import celery_trace

logger = logging.getLogger(__name__)

_SOFT_LIMIT = int(getattr(settings, "LENS_KS_SYNC_SOFT_TIME_LIMIT", 3600))
_TIME_LIMIT = int(getattr(settings, "LENS_KS_SYNC_TIME_LIMIT", 7200))


@shared_task(
    name="apps.lens_bridge.tasks.chat_lifecycle.execute_copilot_chat_provision_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
    soft_time_limit=_SOFT_LIMIT,
    time_limit=_TIME_LIMIT,
)
def execute_copilot_chat_provision_task(self, *, session_link_id: int) -> dict:
    with celery_trace(
        f"copilot-provision-{session_link_id}",
        task_name="apps.lens_bridge.tasks.chat_lifecycle.execute_copilot_chat_provision_task",
    ):
        from apps.lens_bridge.services.chat_lifecycle import run_copilot_chat_provision

        logger.info("copilot chat provision celery started session_link_id=%s", session_link_id)
        result = run_copilot_chat_provision(session_link_id=int(session_link_id))
        logger.info(
            "copilot chat provision celery finished session_link_id=%s status=%s",
            session_link_id,
            result.get("status"),
        )
        return result


@shared_task(
    name="apps.lens_bridge.tasks.chat_lifecycle.execute_copilot_chat_teardown_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    soft_time_limit=_SOFT_LIMIT,
    time_limit=_TIME_LIMIT,
)
def execute_copilot_chat_teardown_task(self, *, session_link_id: int) -> dict:
    with celery_trace(
        f"copilot-teardown-{session_link_id}",
        task_name="apps.lens_bridge.tasks.chat_lifecycle.execute_copilot_chat_teardown_task",
    ):
        from apps.lens_bridge.services.chat_lifecycle import run_copilot_chat_teardown

        logger.info("copilot chat teardown celery started session_link_id=%s", session_link_id)
        result = run_copilot_chat_teardown(session_link_id=int(session_link_id))
        logger.info(
            "copilot chat teardown celery finished session_link_id=%s status=%s",
            session_link_id,
            result.get("status"),
        )
        return result
