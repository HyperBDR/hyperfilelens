"""
Notification subscribers for task lifecycle signals (WS fan-out).
"""

from django.dispatch import receiver

from apps.task.signals import task_updated


@receiver(task_updated)
def on_task_updated(sender, task_uuid, organization_id, status, progress=None, **kwargs):
    from apps.iam.models import Organization
    from apps.notification.channel_push import push_to_org

    org_key = (
        Organization.objects.filter(id=organization_id)
        .values_list("key", flat=True)
        .first()
    )
    if not org_key:
        return
    payload = {
        "type": "task.update",
        "task_uuid": task_uuid,
        "status": status,
    }
    if progress is not None:
        payload["progress"] = progress
    push_to_org(org_key, payload)
