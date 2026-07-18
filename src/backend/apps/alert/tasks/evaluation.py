"""Celery tasks for alert policy evaluation."""

from celery import shared_task

from common.observability.celery_context import logged_celery_task

from apps.alert.services.internal.evaluation import evaluate_all_policies


@shared_task(name="apps.alert.tasks.evaluation.evaluate_alert_policies")
@logged_celery_task(name="apps.alert.tasks.evaluation.evaluate_alert_policies")
def evaluate_alert_policies():
    return evaluate_all_policies()
