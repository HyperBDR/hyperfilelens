"""Public alert service entrypoints."""

from __future__ import annotations

from dataclasses import dataclass

from apps.alert.services.internal.task_events import on_task_finished


@dataclass(frozen=True)
class TaskAlertEmitResult:
    handled: bool


def emit_alert_for_task_uuid(*, task_uuid: str, event_type: str, severity: str = "warning") -> TaskAlertEmitResult | None:
    """Evaluate task alert policies for product task lifecycle signals."""
    del event_type, severity
    on_task_finished(task_uuid=task_uuid)
    return TaskAlertEmitResult(handled=True)
