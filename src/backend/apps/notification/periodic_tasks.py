"""
Register periodic tasks for notification delivery.
"""

from celery.schedules import crontab

from common.scheduling.registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="notification_process_pending_deliveries",
        task="apps.notification.tasks.delivery.process_pending_deliveries",
        schedule=crontab(minute="*/1"),
        args=(),
        kwargs={"limit": 200},
        queue=None,
        enabled=True,
    )
    TASK_REGISTRY.add(
        name="notification_purge_old_records",
        task="apps.notification.tasks.cleanup.purge_old_notification_records",
        schedule=crontab(hour=4, minute=0),
        args=(),
        kwargs={"days_to_keep": 90},
        queue=None,
        enabled=True,
    )

