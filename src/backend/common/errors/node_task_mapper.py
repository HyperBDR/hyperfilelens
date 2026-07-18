from __future__ import annotations

from typing import Any


def map_node_task_failure(
    *,
    kind: str,
    status: str,
    timed_out: bool = False,
) -> str:
    if timed_out or status == "timeout":
        return "AGENT.TIMEOUT"
    kind_norm = (kind or "").strip().lower()
    status_norm = (status or "").strip().lower()
    if status_norm == "canceled":
        return "AGENT.CANCELED"
    if kind_norm == "explorer.list":
        return "AGENT.EXPLORER_LIST_FAILED"
    if kind_norm in {"explorer.validate", "path.validate", "path.info"}:
        return "AGENT.PATH_VALIDATE_FAILED"
    if kind_norm.startswith("nas.") or kind_norm.startswith("mount."):
        return "AGENT.NAS_MOUNT_FAILED"
    if kind_norm == "backup.run":
        return "BACKUP.AGENT_BACKUP_FAILED"
    if status_norm == "failed":
        return "AGENT.TASK_FAILED"
    return "AGENT.TASK_FAILED"


def map_agent_outcome(
    outcome: Any,
    *,
    timed_out: bool = False,
    default_code: str = "AGENT.TASK_FAILED",
) -> str:
    task = getattr(outcome, "task", None)
    kind = str(getattr(task, "kind", "") or "")
    status = str(getattr(task, "status", "") or "")
    if timed_out or getattr(outcome, "timed_out", False):
        return "AGENT.TIMEOUT"
    code = map_node_task_failure(kind=kind, status=status, timed_out=False)
    return code or default_code
