from __future__ import annotations

from celery import shared_task
from django.db import transaction

from common.observability.celery_context import logged_celery_task

from apps.notification.models import NotificationDelivery
from apps.notification.services import attempt_delivery
from apps.audit.services.interface import write_audit_log


@shared_task(name="apps.notification.tasks.delivery.process_pending_deliveries")
@logged_celery_task(name="apps.notification.tasks.delivery.process_pending_deliveries", trace_keys=("limit",))
def process_pending_deliveries(*, limit: int = 200):
    processed = 0
    sent = 0
    failed = 0

    queryset = (
        NotificationDelivery.objects.select_related("channel", "organization")
        .filter(status=NotificationDelivery.Status.PENDING)
        .order_by("created_at", "id")
    )

    for delivery in queryset[: int(limit or 200)]:
        with transaction.atomic():
            locked = (
                NotificationDelivery.objects.select_for_update()
                .select_related("channel", "organization")
                .filter(id=delivery.id)
                .first()
            )
            if locked is None or locked.status != NotificationDelivery.Status.PENDING:
                continue
            result = attempt_delivery(delivery=locked)
            write_audit_log(
                organization=locked.organization,
                user=None,
                action="notification.delivery_attempt",
                target_type="notification_delivery",
                target_id=str(locked.id),
                metadata={
                    "ok": result.ok,
                    "status": locked.status,
                    "channel_type": locked.channel.channel_type,
                    "event_type": locked.event_type,
                },
            )
            processed += 1
            if result.ok:
                sent += 1
            else:
                failed += 1

    return {"processed": processed, "sent": sent, "failed": failed}
