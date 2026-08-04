"""Register periodic tasks for source lifecycle recovery."""

from apps.source import conf as source_conf
from common.scheduling.registry import TASK_REGISTRY


def register_periodic_tasks() -> None:
    TASK_REGISTRY.add(
        name="source_reconcile_backup_pipeline",
        task="apps.source.tasks.pipeline.reconcile_source_pipeline_task",
        schedule=60,
        args=(),
        kwargs={"limit": source_conf.AVAILABILITY_RECONCILE_BATCH_SIZE},
        queue=None,
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="source_reconcile_availability",
        task=(
            "apps.source.tasks.connection_probe."
            "reconcile_source_availability_task"
        ),
        schedule=source_conf.AVAILABILITY_RECONCILE_INTERVAL_SECONDS,
        args=(),
        kwargs={"limit": source_conf.AVAILABILITY_RECONCILE_BATCH_SIZE},
        queue="source.remote-io",
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="source_reconcile_stale_connection_probes",
        task=(
            "apps.source.tasks.connection_probe."
            "reconcile_stale_source_connection_probes_task"
        ),
        schedule=60,
        args=(),
        kwargs={"limit": 100},
        queue="source.remote-io",
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="source_reconcile_stuck_source_unregister_tasks",
        task="apps.source.tasks.source_unregister.reconcile_stuck_source_unregister_tasks_task",
        schedule=60,
        args=(),
        kwargs={"limit": 50},
        queue=None,
        enabled=True,
    )
