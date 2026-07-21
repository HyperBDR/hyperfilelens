from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apps.task.models import Task, TaskEvent
from apps.task.services.interface import append_task_event


CONTROL_PLANE_RESTART_INTERRUPTED = "CONTROL_PLANE_RESTART_INTERRUPTED"
MAX_AUTOMATIC_REPLACEMENTS = 3


class RecoveryDecision(StrEnum):
    WAIT = "wait"
    RESUME = "resume"
    FAIL = "fail"
    FAIL_AND_REPLACE = "fail_and_replace"


@dataclass(frozen=True)
class RecoveryPlan:
    decision: RecoveryDecision
    reason: str
    evidence: dict[str, Any]


def record_recovery_decision(
    *,
    task: Task,
    plan: RecoveryPlan,
    replacement_task: Task | None = None,
) -> None:
    metadata = {
        "decision": plan.decision.value,
        "reason": plan.reason,
        "evidence": plan.evidence,
        "recovery_attempt": int(task.recovery_attempt or 0),
    }
    if replacement_task is not None:
        metadata["replacement_task_uuid"] = str(replacement_task.task_uuid)
    append_task_event(
        task=task,
        level=(
            TaskEvent.Level.WARN
            if plan.decision in {RecoveryDecision.FAIL, RecoveryDecision.FAIL_AND_REPLACE}
            else TaskEvent.Level.INFO
        ),
        message=f"Control-plane recovery decision: {plan.decision.value}",
        metadata=metadata,
    )
