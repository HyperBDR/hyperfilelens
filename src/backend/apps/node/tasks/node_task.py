"""
Celery tasks for the ``NodeTask`` watchdog.

Runs more frequently than the 10s per-task watchdog so overdue tasks are
marked ``timeout`` and ``task.cancel`` is sent to the Agent.
"""

from __future__ import annotations

import logging

from celery import shared_task

from common.observability.celery_context import logged_celery_task

from apps.node import conf as node_conf
from apps.node.constants import TASK_REDELIVER_AGENT_TASK, TASK_SWEEP_NODE_TASK_WATCHDOG
from apps.node.services.interface import redeliver_pending_agent_task, sweep_watchdog_timeouts

logger = logging.getLogger(__name__)


@shared_task(
    name=TASK_SWEEP_NODE_TASK_WATCHDOG,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
@logged_celery_task(name=TASK_SWEEP_NODE_TASK_WATCHDOG, trace_keys=("limit",))
def sweep_node_task_watchdog(self, *, limit: int = 500) -> dict[str, int]:
    marked = sweep_watchdog_timeouts(limit=int(limit))
    if marked:
        logger.info(
            "sweep_node_task_watchdog complete marked=%s limit=%s watchdog_seconds=%s",
            marked,
            limit,
            node_conf.TASK_WATCHDOG_SECONDS,
        )
    else:
        logger.debug(
            "sweep_node_task_watchdog complete marked=%s limit=%s",
            marked,
            limit,
        )
    return {
        "marked_timeout": marked,
        "watchdog_seconds": node_conf.TASK_WATCHDOG_SECONDS,
    }


@shared_task(
    name=TASK_REDELIVER_AGENT_TASK,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def redeliver_agent_task(self, *, task_id: str) -> dict[str, str]:
    task = redeliver_pending_agent_task(task_id=task_id)
    if task is None:
        return {"task_id": task_id, "status": "missing"}
    return {
        "task_id": str(task.id),
        "status": task.status,
        "last_error": task.last_error or "",
    }
