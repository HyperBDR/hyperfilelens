"""Alert subscribers for cross-app task lifecycle signals."""

from django.dispatch import receiver

from apps.task.signals import task_failed, task_timed_out


@receiver(task_failed)
def on_task_failed(sender, task_uuid, event_type="task_failed", severity="warning", **kwargs):
    from apps.alert.services.interface import emit_alert_for_task_uuid

    emit_alert_for_task_uuid(task_uuid=task_uuid, event_type=event_type, severity=severity)


@receiver(task_timed_out)
def on_task_timed_out(sender, task_uuid, event_type="task_timeout", severity="critical", **kwargs):
    from apps.alert.services.interface import emit_alert_for_task_uuid

    emit_alert_for_task_uuid(task_uuid=task_uuid, event_type=event_type, severity=severity)
