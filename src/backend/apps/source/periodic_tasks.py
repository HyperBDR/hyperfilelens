"""Register periodic tasks for source lifecycle recovery."""

from common.scheduling.registry import TASK_REGISTRY


def register_periodic_tasks() -> None:
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
