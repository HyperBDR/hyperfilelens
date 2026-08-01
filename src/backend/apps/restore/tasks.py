from celery import shared_task

from apps.restore.services.reconciliation import reconcile_restore_node_task_projections


@shared_task(name="apps.restore.tasks.reconcile_restore_node_task_projections")
def reconcile_restore_node_task_projections_task(*, limit: int = 200) -> dict[str, int]:
    return reconcile_restore_node_task_projections(limit=limit)
