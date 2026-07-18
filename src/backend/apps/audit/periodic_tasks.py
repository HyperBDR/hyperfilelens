"""Register periodic tasks for audit retention."""

from celery.schedules import crontab

from common.scheduling.registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="audit_purge_old_logs",
        task="apps.audit.tasks.cleanup.purge_old_audit_logs",
        schedule=crontab(hour=4, minute=30),
        args=(),
        kwargs={"days_to_keep": 365},
        queue=None,
        enabled=True,
    )
