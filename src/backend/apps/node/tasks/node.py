"""
Celery tasks for ``Node`` registry hygiene.

Reconciles nodes stuck ``online`` when Redis ``agent_loc`` / ``node_alive`` expired.
"""

from __future__ import annotations

import logging

from celery import shared_task

from common.observability.celery_context import logged_celery_task

from apps.node.constants import TASK_RECONCILE_STALE_ONLINE_NODES
from apps.node.services.interface import reconcile_stale_online_nodes

logger = logging.getLogger(__name__)


@shared_task(
    name=TASK_RECONCILE_STALE_ONLINE_NODES,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
@logged_celery_task(name=TASK_RECONCILE_STALE_ONLINE_NODES, trace_keys=("limit",))
def reconcile_stale_online_nodes_task(self, *, limit: int = 200) -> dict[str, int]:
    summary = reconcile_stale_online_nodes(limit=int(limit))
    if summary.get("nodes_marked_offline") or summary.get("tasks_failed"):
        logger.info("reconcile_stale_online_nodes complete %s", summary)
    else:
        logger.debug("reconcile_stale_online_nodes complete %s", summary)
    return summary
