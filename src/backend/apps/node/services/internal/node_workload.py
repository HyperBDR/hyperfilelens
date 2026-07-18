"""Active backup/restore workload guards for node lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.selectors.internal.node_task_query import active_node_tasks_for_node
from apps.node.services.internal.task_offline_reconcile import (
    product_task_blocks_cleanup,
)
from apps.task.models import Task, TaskResource

_ACTIVE_TASK_STATUSES = frozenset({Task.Status.PENDING, Task.Status.RUNNING})
_LIFECYCLE_NODE_TASK_KINDS = frozenset({"agent.upgrade", "agent.uninstall"})


@dataclass(frozen=True)
class NodeWorkloadBlocker:
    code: str
    task_uuid: str
    task_type: str
    label: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "task_uuid": self.task_uuid,
            "task_type": self.task_type,
            "label": self.label,
        }


def _task_label(task: Task) -> str:
    name = str(task.display_name or "").strip()
    task_type = str(task.task_type or "").strip()
    if name:
        return f"{task_type} · {name}" if task_type else name
    return task_type or str(task.task_uuid)


def _backup_tasks_for_agent(*, organization_id: int, node_id: int):
    by_payload = Task.objects.filter(
        organization_id=organization_id,
        task_type=Task.Type.BACKUP,
        status__in=_ACTIVE_TASK_STATUSES,
    ).order_by("-created_at", "-id")
    for task in by_payload:
        payload = task.request_payload if isinstance(task.request_payload, dict) else {}
        if (
            str(payload.get("source_type") or "") == "agent"
            and int(payload.get("source_ref_id") or 0) == node_id
        ):
            yield task

    yield from Task.objects.filter(
        organization_id=organization_id,
        task_type=Task.Type.BACKUP,
        status__in=_ACTIVE_TASK_STATUSES,
        resources__resource_type=TaskResource.Type.BACKUP_SOURCE,
        resources__resource_subtype="agent",
        resources__resource_id=node_id,
    ).order_by("-created_at", "-id").distinct()


def _restore_tasks_for_agent(*, organization_id: int, node_id: int):
    from apps.restore.models import RestoreRecord

    task_ids = RestoreRecord.objects.filter(
        organization_id=organization_id,
        target_type="agent",
        target_ref_id=node_id,
    ).values_list("task_id", flat=True)
    if not task_ids:
        return
    yield from Task.objects.filter(
        pk__in=task_ids,
        organization_id=organization_id,
        task_type=Task.Type.RESTORE,
        status__in=_ACTIVE_TASK_STATUSES,
    ).order_by("-created_at", "-id")


def _backup_tasks_for_proxy(*, organization_id: int, node_id: int):
    from apps.storage.repositories.models import Repository

    repo_ids = list(
        Repository.objects.filter(
            organization_id=organization_id,
            bind_node_type=Repository.BindNodeType.PROXY,
            bind_node_id=node_id,
        )
        .exclude(status=Repository.Status.REMOVED)
        .values_list("id", flat=True)
    )
    if not repo_ids:
        return
    yield from Task.objects.filter(
        organization_id=organization_id,
        task_type=Task.Type.BACKUP,
        status__in=_ACTIVE_TASK_STATUSES,
        resources__resource_type=TaskResource.Type.REPOSITORY,
        resources__resource_id__in=repo_ids,
    ).order_by("-created_at", "-id").distinct()


def _execution_node_tasks(*, org, node_id: int):
    for task in active_node_tasks_for_node(org=org, node=node_id):
        if task.kind in _LIFECYCLE_NODE_TASK_KINDS:
            continue
        yield task


def get_node_workload_blockers(*, node: Node) -> list[NodeWorkloadBlocker]:
    """Return active backup/restore (and execution) blockers for lifecycle ops."""
    org = node.organization
    organization_id = node.organization_id
    node_id = node.id
    blockers: list[NodeWorkloadBlocker] = []
    seen: set[str] = set()

    def add_task_blocker(*, task: Task, code: str) -> None:
        key = str(task.task_uuid)
        if key in seen:
            return
        seen.add(key)
        blockers.append(
            NodeWorkloadBlocker(
                code=code,
                task_uuid=key,
                task_type=str(task.task_type or ""),
                label=_task_label(task),
            )
        )

    if node.role == NodeRole.AGENT:
        for task in _backup_tasks_for_agent(organization_id=organization_id, node_id=node_id):
            if product_task_blocks_cleanup(task=task):
                add_task_blocker(task=task, code="backup_running")
        for task in _restore_tasks_for_agent(organization_id=organization_id, node_id=node_id):
            if product_task_blocks_cleanup(task=task):
                add_task_blocker(task=task, code="restore_running")
    elif node.role == NodeRole.PROXY:
        for task in _backup_tasks_for_proxy(organization_id=organization_id, node_id=node_id):
            if product_task_blocks_cleanup(task=task):
                add_task_blocker(task=task, code="backup_running")

    for node_task in _execution_node_tasks(org=org, node_id=node_id):
        blockers.append(
            NodeWorkloadBlocker(
                code="node_task_running",
                task_uuid=str(node_task.id),
                task_type=str(node_task.kind or ""),
                label=str(node_task.kind or "node_task"),
            )
        )

    return blockers


def node_workload_payload(*, node: Node) -> dict[str, Any]:
    reasons = get_node_workload_blockers(node=node)
    return {
        "blocked": bool(reasons),
        "reasons": [item.to_payload() for item in reasons],
    }


def assert_node_available_for_lifecycle(*, node: Node) -> None:
    from apps.node.exceptions import NodeLifecycleError

    reasons = get_node_workload_blockers(node=node)
    if reasons:
        raise NodeLifecycleError(
            "Node has active backup, restore, or execution tasks.",
            code="node_workload_active",
            blockers=[item.to_payload() for item in reasons],
        )
