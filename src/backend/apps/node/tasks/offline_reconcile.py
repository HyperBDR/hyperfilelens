"""Periodic reconciliation for offline-stale node tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from common.observability.celery_context import logged_celery_task

from apps.node.constants import (
    TASK_RECONCILE_EXECUTION_STATE,
    TASK_RECONCILE_OFFLINE_STALE_NODE_TASKS,
)
from apps.node.services.internal.task_offline_reconcile import (
    reconcile_execution_state_for_active_tasks,
    reconcile_offline_stale_node_tasks,
)

logger = logging.getLogger(__name__)


@shared_task(
    name=TASK_RECONCILE_OFFLINE_STALE_NODE_TASKS,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
@logged_celery_task(name=TASK_RECONCILE_OFFLINE_STALE_NODE_TASKS, trace_keys=("limit",))
def reconcile_offline_stale_node_tasks_task(self, *, limit: int = 100) -> dict[str, int]:
    summary = reconcile_offline_stale_node_tasks(limit=int(limit))
    if summary.get("node_tasks_failed"):
        logger.info("reconcile_offline_stale_node_tasks_task complete %s", summary)
    return summary


@shared_task(
    name=TASK_RECONCILE_EXECUTION_STATE,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
@logged_celery_task(name=TASK_RECONCILE_EXECUTION_STATE, trace_keys=("limit",))
def reconcile_execution_state_task(self, *, limit: int = 200) -> dict[str, int]:
    summary = reconcile_execution_state_for_active_tasks(limit=int(limit))
    if summary.get("execution_state_updated"):
        logger.info("reconcile_execution_state_task complete %s", summary)
    return summary
