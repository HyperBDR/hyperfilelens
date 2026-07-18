"""Audit log retention."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from common.observability.celery_context import logged_celery_task

from apps.audit.models import AuditLog


@shared_task(name="apps.audit.tasks.cleanup.purge_old_audit_logs")
@logged_celery_task(name="apps.audit.tasks.cleanup.purge_old_audit_logs", trace_keys=("days_to_keep",))
def purge_old_audit_logs(*, days_to_keep: int = 365):
    cutoff = timezone.now() - timedelta(days=int(days_to_keep))
    deleted, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
    return {"deleted": deleted}
