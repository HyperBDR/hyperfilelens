"""Register periodic tasks for alert evaluation."""

from celery.schedules import crontab

from common.scheduling.registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="alert_evaluate_policies",
        task="apps.alert.tasks.evaluation.evaluate_alert_policies",
        schedule=crontab(minute="*/1"),
        args=(),
        kwargs={},
        queue=None,
        enabled=True,
    )
