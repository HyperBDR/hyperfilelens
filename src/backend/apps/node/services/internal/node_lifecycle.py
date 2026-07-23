"""Node lifecycle operations: async upgrade/remove with derived console state."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.iam.models import Organization
from apps.node import conf as node_conf
from apps.node.exceptions import AgentUpgradeError, NodeLifecycleError
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.node.selectors.interface import get_node_task_runtime_info
from apps.node.selectors.internal.node_task_query import node_tasks_queryset
from apps.node.services.internal.agent_release import agent_version_compare, is_agent_artifact_id
from apps.node.services.internal.agent_task import run_agent_task_async
from apps.node.services.internal.agent_uninstall import (
    _purge_agent_server_records,
)
from apps.node.services.internal.agent_upgrade import validate_agent_upgrade
from apps.node.services.internal.node_registry import agent_session_registered, agent_ws_routable
from apps.node.services.internal.node_workload import (
    assert_node_available_for_lifecycle,
    get_node_workload_blockers,
    node_workload_payload,
)

logger = logging.getLogger(__name__)

LIFECYCLE_KIND_UPGRADE = "upgrade"
LIFECYCLE_KIND_REMOVE = "remove"
_LIFECYCLE_TASK_KINDS = {
    LIFECYCLE_KIND_UPGRADE: "agent.upgrade",
    LIFECYCLE_KIND_REMOVE: "agent.uninstall",
}
_ACTIVE_TASK_STATUSES = frozenset(
    {NodeTask.Status.PENDING, NodeTask.Status.RUNNING},
)
_TERMINAL_TASK_STATUSES = frozenset(
    {
        NodeTask.Status.SUCCESS,
        NodeTask.Status.FAILED,
        NodeTask.Status.TIMEOUT,
        NodeTask.Status.CANCELED,
    },
)


def _correlation_id(*, node_id: int, kind: str) -> str:
    return f"{kind}:{node_id}"


def _latest_lifecycle_task(*, org: Organization, node: Node, kind: str) -> NodeTask | None:
    return (
        node_tasks_queryset(
            organization_id=org.id,
            node_id=node.id,
            kind=_LIFECYCLE_TASK_KINDS[kind],
            correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
            correlation_id=_correlation_id(node_id=node.id, kind=kind),
        )
        .first()
    )


def _active_lifecycle_task(*, org: Organization, node: Node) -> NodeTask | None:
    for kind in (LIFECYCLE_KIND_UPGRADE, LIFECYCLE_KIND_REMOVE):
        task = _latest_lifecycle_task(org=org, node=node, kind=kind)
        if task is not None and task.status in _ACTIVE_TASK_STATUSES:
            return task
    return None


def _task_progress_phase(task: NodeTask) -> str | None:
    runtime = get_node_task_runtime_info(task_id=str(task.id)) or {}
    progress = runtime.get("progress")
    if isinstance(progress, dict):
        phase = progress.get("phase")
        if phase:
            return str(phase)
    result = task.result if isinstance(task.result, dict) else {}
    mode = result.get("mode")
    if mode:
        return str(mode)
    return None


def _target_version_from_task(task: NodeTask) -> str:
    result = task.result if isinstance(task.result, dict) else {}
    target = str(result.get("target_version") or "").strip()
    if target:
        return target
    payload = task.payload if isinstance(task.payload, dict) else {}
    return str(payload.get("target_version") or "").strip()


def _node_installed_version(node: Node) -> str:
    version = str(node.version or "").strip()
    if version:
        return version
    meta = node.metadata if isinstance(node.metadata, dict) else {}
    inv = meta.get("inventory")
    if isinstance(inv, dict):
        return str(inv.get("agent_version") or "").strip()
    return str(meta.get("agent_version") or "").strip()


def _version_matches_target(*, node: Node, target_version: str) -> bool:
    current = _node_installed_version(node)
    if not is_agent_artifact_id(target_version) or not is_agent_artifact_id(current):
        return False
    return agent_version_compare(current, target_version) >= 0


def _is_detached_lifecycle_task(task: NodeTask) -> bool:
    if task.kind not in _LIFECYCLE_TASK_KINDS.values():
        return False
    result = task.result if isinstance(task.result, dict) else {}
    if str(result.get("mode") or "").strip() == "local_detached":
        return True
    progress = result.get("last_progress")
    if isinstance(progress, dict) and str(progress.get("mode") or "").strip() == "local_detached":
        return True
    return False


def _detached_at_from_task(task: NodeTask) -> timezone.datetime | None:
    result = task.result if isinstance(task.result, dict) else {}
    raw = result.get("detached_at")
    if raw:
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(str(raw))
        if parsed is not None:
            if timezone.is_naive(parsed):
                return timezone.make_aware(parsed)
            return parsed
    if _is_detached_lifecycle_task(task):
        return task.updated_at or task.created_at
    return None


def _elapsed_since_detached(task: NodeTask) -> timedelta | None:
    detached_at = _detached_at_from_task(task)
    if detached_at is None:
        return None
    return timezone.now() - detached_at


def _node_disk_metrics(node: Node) -> tuple[int | None, int | None]:
    meta = node.metadata if isinstance(node.metadata, dict) else {}
    inv = meta.get("inventory")
    if not isinstance(inv, dict):
        inv = meta
    if not isinstance(inv, dict):
        return None, None
    total_raw = inv.get("disk_total_bytes")
    free_raw = inv.get("disk_free_bytes")
    total = int(total_raw) if total_raw not in (None, "") else None
    free = int(free_raw) if free_raw not in (None, "") else None
    if total is not None and total <= 0:
        total = None
    if free is not None and free < 0:
        free = None
    return total, free


def _disk_blocks_upgrade(node: Node) -> bool:
    total, free = _node_disk_metrics(node)
    min_free = int(node_conf.UPGRADE_MIN_FREE_BYTES)
    if free is not None and free < min_free:
        return True
    if total and free is not None and total > 0:
        used_pct = ((total - free) / total) * 100
        if used_pct > float(node_conf.UPGRADE_MAX_DISK_USED_PCT):
            return True
    return False


def _running_lifecycle_task(
    *,
    org: Organization,
    node: Node,
    kind: str,
) -> NodeTask | None:
    task = _latest_lifecycle_task(org=org, node=node, kind=kind)
    if task is not None and task.status in _ACTIVE_TASK_STATUSES:
        return task
    return None


def _verify_started_at_from_task(task: NodeTask) -> timezone.datetime | None:
    result = task.result if isinstance(task.result, dict) else {}
    raw = result.get("verify_started_at")
    if not raw:
        return None
    from django.utils.dateparse import parse_datetime

    parsed = parse_datetime(str(raw))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _persist_upgrade_task_result(
    *,
    node: Node,
    task: NodeTask,
    result_patch: dict[str, Any],
) -> NodeTask:
    from apps.node.services.internal.task import complete_task

    merged = dict(task.result or {})
    for key, value in result_patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return complete_task(
        task_id=task.id,
        node_id=node.id,
        status=NodeTask.Status.RUNNING,
        result=merged,
        replace_result=True,
    )


def _clear_upgrade_verify_clock(*, node: Node, task: NodeTask) -> NodeTask:
    result = task.result if isinstance(task.result, dict) else {}
    if not result.get("verify_started_at"):
        return task
    return _persist_upgrade_task_result(
        node=node,
        task=task,
        result_patch={"verify_started_at": None},
    )


def _upgrade_verify_ready(*, node: Node, task: NodeTask) -> bool:
    if not _is_detached_lifecycle_task(task):
        return False
    if not agent_session_registered(agent_id=node.id):
        return False
    if node.status != Node.Status.ONLINE:
        return False
    target_version = _target_version_from_task(task)
    if not target_version:
        return False
    return _version_matches_target(node=node, target_version=target_version)


def _advance_upgrade_verify(*, node: Node, task: NodeTask) -> bool:
    """
    Finalize detached upgrade only after WS + version stayed stable long enough.

    Returns True when the task was marked SUCCESS.
    """
    if task.kind != _LIFECYCLE_TASK_KINDS[LIFECYCLE_KIND_UPGRADE]:
        return False
    if task.status not in _ACTIVE_TASK_STATUSES:
        return False

    if not _upgrade_verify_ready(node=node, task=task):
        _clear_upgrade_verify_clock(node=node, task=task)
        return False

    verify_started = _verify_started_at_from_task(task)
    now = timezone.now()
    if verify_started is None:
        task = _persist_upgrade_task_result(
            node=node,
            task=task,
            result_patch={"verify_started_at": now.isoformat()},
        )
        verify_started = now

    stable_for = now - verify_started
    if stable_for < timedelta(seconds=node_conf.UPGRADE_STABLE_SECONDS):
        return False

    from apps.node.services.internal.task import complete_task

    merged = dict(task.result or {})
    merged["verified"] = True
    merged.pop("verify_started_at", None)
    complete_task(
        task_id=task.id,
        node_id=node.id,
        status=NodeTask.Status.SUCCESS,
        result=merged,
    )
    logger.info(
        "node lifecycle upgrade verified after stable reconnect node_id=%s task_id=%s stable_seconds=%s",
        node.id,
        task.id,
        int(stable_for.total_seconds()),
    )
    return True


def _finalize_upgrade_on_reconnect(*, node: Node, task: NodeTask) -> bool:
    return _advance_upgrade_verify(node=node, task=task)


def _fail_stale_upgrade_task(*, node: Node, task: NodeTask) -> bool:
    if task.kind != _LIFECYCLE_TASK_KINDS[LIFECYCLE_KIND_UPGRADE]:
        return False
    if task.status not in _ACTIVE_TASK_STATUSES:
        return False
    if not _is_detached_lifecycle_task(task):
        return False
    detached_at = _detached_at_from_task(task)
    if detached_at is None:
        return False
    if timezone.now() - detached_at < timedelta(
        seconds=node_conf.LIFECYCLE_DETACHED_TIMEOUT_SECONDS,
    ):
        return False
    target_version = _target_version_from_task(task)
    if target_version and _version_matches_target(node=node, target_version=target_version):
        if _advance_upgrade_verify(node=node, task=task):
            return True

    from apps.node.services.internal.task import complete_task

    complete_task(
        task_id=task.id,
        node_id=node.id,
        status=NodeTask.Status.FAILED,
        error="Upgrade timed out waiting for agent to reconnect.",
        result=dict(task.result or {}),
    )
    logger.warning(
        "node lifecycle upgrade timed out node_id=%s task_id=%s",
        node.id,
        task.id,
    )
    return True


def _upgrade_lifecycle_payload(
    *,
    org: Organization,
    node: Node,
    task: NodeTask | None,
) -> dict[str, Any] | None:
    if task is None:
        return None

    target_version = _target_version_from_task(task)
    if not target_version and task.status in _ACTIVE_TASK_STATUSES:
        try:
            target_version = validate_agent_upgrade(node=node)
        except Exception:
            target_version = ""

    base: dict[str, Any] = {
        "kind": LIFECYCLE_KIND_UPGRADE,
        "task_id": str(task.id),
        "target_version": target_version,
        "started_at": task.created_at.isoformat() if task.created_at else None,
    }

    if task.status in _ACTIVE_TASK_STATUSES:
        phase = _task_progress_phase(task) or "dispatching"
        if _is_detached_lifecycle_task(task):
            if agent_session_registered(agent_id=node.id):
                if target_version and _version_matches_target(
                    node=node,
                    target_version=target_version,
                ):
                    return {**base, "state": "verifying", "phase": "waiting_for_version"}
                return {**base, "state": "upgrading", "phase": phase}
            return {
                **base,
                "state": "restarting",
                "phase": phase or "waiting_for_agent",
            }
        return {
            **base,
            "state": "upgrading",
            "phase": phase,
        }

    if task.status in {NodeTask.Status.FAILED, NodeTask.Status.TIMEOUT, NodeTask.Status.CANCELED}:
        return {
            **base,
            "state": "failed",
            "phase": "failed",
            "error": task.last_error or task.status,
        }

    if task.status != NodeTask.Status.SUCCESS:
        return None

    if target_version and _version_matches_target(node=node, target_version=target_version):
        return None

    return {**base, "state": "verifying", "phase": "waiting_for_version"}


def _remove_lifecycle_payload(
    *,
    node: Node,
    task: NodeTask | None,
) -> dict[str, Any] | None:
    if task is None:
        return None

    base: dict[str, Any] = {
        "kind": LIFECYCLE_KIND_REMOVE,
        "task_id": str(task.id),
        "started_at": task.created_at.isoformat() if task.created_at else None,
    }

    if task.status in _ACTIVE_TASK_STATUSES:
        phase = _task_progress_phase(task) or "dispatching"
        if _is_detached_lifecycle_task(task) and not agent_ws_routable(agent_id=node.id):
            elapsed = _elapsed_since_detached(task)
            finalize_after = timedelta(seconds=node_conf.REMOVE_FINALIZE_SECONDS)
            if elapsed is not None and elapsed >= finalize_after:
                return {
                    **base,
                    "state": "cleaning_up",
                    "phase": "agent_disconnected",
                }
            return {
                **base,
                "state": "removing",
                "phase": phase or "waiting_for_agent",
            }
        return {
            **base,
            "state": "removing",
            "phase": phase,
        }

    if task.status in {NodeTask.Status.FAILED, NodeTask.Status.TIMEOUT, NodeTask.Status.CANCELED}:
        return {
            **base,
            "state": "failed",
            "phase": "failed",
            "error": task.last_error or task.status,
        }

    if task.status != NodeTask.Status.SUCCESS:
        return None

    if agent_ws_routable(agent_id=node.id):
        finished = task.updated_at or task.created_at
        grace = timedelta(seconds=node_conf.REMOVE_PURGE_GRACE_SECONDS)
        if finished and timezone.now() - finished < grace:
            return {**base, "state": "removing", "phase": "waiting_for_disconnect"}
        # Grace elapsed but still routable — proceed to cleanup anyway.

    return {**base, "state": "cleaning_up", "phase": "purging_records"}


def _finalize_remove_task_if_agent_disconnected(*, node: Node, task: NodeTask) -> bool:
    """
    Uninstall stops the agent process and tears down its WSS session.

    Finalize only after detached uninstall was scheduled and WS stayed gone
    long enough for the script to run.
    """
    if task.kind != "agent.uninstall":
        return False
    if task.status != NodeTask.Status.RUNNING:
        return False
    if not _is_detached_lifecycle_task(task):
        return False
    if agent_ws_routable(agent_id=node.id):
        return False
    elapsed = _elapsed_since_detached(task)
    if elapsed is None or elapsed < timedelta(seconds=node_conf.REMOVE_FINALIZE_SECONDS):
        return False

    from apps.node.services.internal.task import complete_task

    merged = dict(task.result or {})
    merged["mode"] = "local_detached"
    merged["finalized"] = True
    complete_task(
        task_id=task.id,
        node_id=node.id,
        status=NodeTask.Status.SUCCESS,
        result=merged,
    )
    logger.info(
        "node lifecycle remove finalized after agent disconnect node_id=%s task_id=%s",
        node.id,
        task.id,
    )
    return True


def compute_node_lifecycle(*, org: Organization, node: Node) -> dict[str, Any] | None:
    remove_task = _latest_lifecycle_task(org=org, node=node, kind=LIFECYCLE_KIND_REMOVE)
    if remove_task is not None:
        payload = _remove_lifecycle_payload(node=node, task=remove_task)
        if payload is not None:
            return payload

    upgrade_task = _latest_lifecycle_task(org=org, node=node, kind=LIFECYCLE_KIND_UPGRADE)
    if upgrade_task is not None:
        return _upgrade_lifecycle_payload(org=org, node=node, task=upgrade_task)

    return None


def advance_node_lifecycle(
    *,
    org: Organization,
    node: Node,
    user=None,
) -> dict[str, Any] | None:
    """
    Advance lifecycle when agent WS drops during detached upgrade/remove.
    Returns purge summary when remove records were removed.
    """
    upgrade_task = _running_lifecycle_task(org=org, node=node, kind=LIFECYCLE_KIND_UPGRADE)
    if upgrade_task is not None:
        if _finalize_upgrade_on_reconnect(node=node, task=upgrade_task):
            upgrade_task.refresh_from_db()
        else:
            _fail_stale_upgrade_task(node=node, task=upgrade_task)

    remove_task = _latest_lifecycle_task(org=org, node=node, kind=LIFECYCLE_KIND_REMOVE)
    if remove_task is None:
        return None

    if _finalize_remove_task_if_agent_disconnected(node=node, task=remove_task):
        remove_task.refresh_from_db()

    payload = _remove_lifecycle_payload(node=node, task=remove_task)
    if payload is None or payload.get("state") != "cleaning_up":
        return None

    if node.is_deleted:
        return {"node_id": node.id, "already_removed": True}

    summary = _purge_agent_server_records(org=org, node=node, user=user)
    summary.update({"node_id": node.id, "purged": True})
    logger.info("node lifecycle remove purged node_id=%s", node.id)
    return summary


def start_node_upgrade(
    *,
    org: Organization,
    node: Node,
    user=None,
) -> dict[str, Any]:
    if node.role not in (NodeRole.AGENT, NodeRole.PROXY, NodeRole.GATEWAY):
        raise NodeLifecycleError("Only enrolled agents support remote upgrade.", code="role_not_managed")

    active = _active_lifecycle_task(org=org, node=node)
    if active is not None:
        raise NodeLifecycleError(
            "Node already has an active lifecycle operation.",
            code="lifecycle_in_progress",
        )

    assert_node_available_for_lifecycle(node=node)

    try:
        target_version = validate_agent_upgrade(node=node)
    except AgentUpgradeError as exc:
        raise NodeLifecycleError(str(exc), code=exc.code) from exc
    handle = run_agent_task_async(
        org=org,
        node_id=node.id,
        kind="agent.upgrade",
        payload={"target_version": target_version},
        correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
        correlation_id=_correlation_id(node_id=node.id, kind=LIFECYCLE_KIND_UPGRADE),
    )
    task = handle.task
    logger.info(
        "node lifecycle dispatch kind=%s node_id=%s task_id=%s target_version=%s",
        LIFECYCLE_KIND_UPGRADE,
        node.id,
        task.id,
        target_version,
    )
    return {
        "operation_id": str(task.id),
        "task_id": str(task.id),
        "node_id": node.id,
        "kind": LIFECYCLE_KIND_UPGRADE,
        "state": "upgrading",
        "phase": "dispatching",
        "target_version": target_version,
    }


def start_node_remove(
    *,
    org: Organization,
    node: Node,
    user=None,
    force: bool = False,
) -> dict[str, Any]:
    if node.role not in (NodeRole.AGENT, NodeRole.PROXY, NodeRole.GATEWAY):
        raise NodeLifecycleError("Only enrolled agents support remote removal.", code="role_not_managed")

    active = _active_lifecycle_task(org=org, node=node)
    if active is not None:
        raise NodeLifecycleError(
            "Node already has an active lifecycle operation.",
            code="lifecycle_in_progress",
        )

    assert_node_available_for_lifecycle(node=node)

    if node.role == NodeRole.PROXY:
        from apps.node.services.internal.bindings import collect_proxy_bindings

        bindings = collect_proxy_bindings(
            organization_id=org.id,
            proxy_id=node.id,
        )
        if not bindings.is_empty():
            if not force:
                raise NodeLifecycleError(
                    "Proxy has bound resources. Replace them before deletion.",
                    code="proxy_has_bindings",
                )
            from apps.node.services.internal.proxy_decommission import (
                ProxyDecommissionBlocked,
                force_cleanup_proxy_bindings,
            )

            try:
                force_cleanup_proxy_bindings(org=org, proxy=node, user=user)
            except ProxyDecommissionBlocked as exc:
                raise NodeLifecycleError(str(exc), code=exc.code) from exc

    if not agent_ws_routable(agent_id=node.id):
        summary = _purge_agent_server_records(org=org, node=node, user=user)
        return {
            "operation_id": f"offline-remove:{node.id}",
            "task_id": None,
            "node_id": node.id,
            "kind": LIFECYCLE_KIND_REMOVE,
            "state": "completed",
            "phase": "offline_purged",
            "offline": True,
            "purged": True,
            "summary": summary,
        }

    handle = run_agent_task_async(
        org=org,
        node_id=node.id,
        kind="agent.uninstall",
        payload={"keep_data": False},
        correlation_type=node_conf.LIFECYCLE_CORRELATION_TYPE,
        correlation_id=_correlation_id(node_id=node.id, kind=LIFECYCLE_KIND_REMOVE),
    )
    task = handle.task
    logger.info(
        "node lifecycle dispatch kind=%s node_id=%s task_id=%s offline=%s",
        LIFECYCLE_KIND_REMOVE,
        node.id,
        task.id,
        False,
    )
    return {
        "operation_id": str(task.id),
        "task_id": str(task.id),
        "node_id": node.id,
        "kind": LIFECYCLE_KIND_REMOVE,
        "state": "removing",
        "phase": "dispatching",
        "offline": False,
    }


def preview_batch_operations(
    *,
    org: Organization,
    node_ids: list[int],
    kind: str,
) -> dict[str, Any]:
    if kind not in {LIFECYCLE_KIND_UPGRADE, LIFECYCLE_KIND_REMOVE}:
        raise NodeLifecycleError("Unsupported lifecycle kind.", code="invalid_kind")

    nodes = list(
        Node.objects.filter(
            organization_id=org.id,
            pk__in=node_ids,
            is_deleted=False,
        ).order_by("name", "id")
    )
    found_ids = {node.id for node in nodes}
    missing = [node_id for node_id in node_ids if node_id not in found_ids]

    eligible: list[dict[str, Any]] = []
    skipped_offline: list[dict[str, Any]] = []
    skipped_workload: list[dict[str, Any]] = []
    skipped_in_progress: list[dict[str, Any]] = []
    skipped_not_upgradeable: list[dict[str, Any]] = []
    skipped_proxy_bound: list[dict[str, Any]] = []
    skipped_disk_full: list[dict[str, Any]] = []

    for node in nodes:
        item = {"node_id": node.id, "name": node.name}
        if _active_lifecycle_task(org=org, node=node):
            skipped_in_progress.append({**item, "reason": "lifecycle_in_progress"})
            continue

        blockers = get_node_workload_blockers(node=node)
        if blockers:
            skipped_workload.append(
                {
                    **item,
                    "reason": "node_workload_active",
                    "blockers": [b.to_payload() for b in blockers],
                }
            )
            continue

        if kind == LIFECYCLE_KIND_UPGRADE:
            if node.status != Node.Status.ONLINE or not agent_ws_routable(agent_id=node.id):
                skipped_offline.append({**item, "reason": "offline"})
                continue
            if _disk_blocks_upgrade(node):
                skipped_disk_full.append({**item, "reason": "disk_full"})
                continue
            try:
                target_version = validate_agent_upgrade(node=node)
            except Exception as exc:
                code = getattr(exc, "code", "not_upgradeable")
                if code == "node_offline":
                    skipped_offline.append({**item, "reason": "offline"})
                else:
                    skipped_not_upgradeable.append(
                        {**item, "reason": code, "message": str(exc)}
                    )
                continue
            eligible.append({**item, "target_version": target_version})
            continue

        if kind == LIFECYCLE_KIND_REMOVE:
            if node.role == NodeRole.PROXY:
                from apps.node.services.internal.bindings import collect_proxy_bindings

                bindings = collect_proxy_bindings(
                    organization_id=org.id,
                    proxy_id=node.id,
                )
                if not bindings.is_empty():
                    skipped_proxy_bound.append({**item, "reason": "proxy_has_bindings"})
                    continue
            if not agent_ws_routable(agent_id=node.id):
                eligible.append({**item, "offline": True})
            else:
                eligible.append({**item, "offline": False})
            continue

    return {
        "kind": kind,
        "requested": len(node_ids),
        "eligible": eligible,
        "skipped_offline": skipped_offline,
        "skipped_workload": skipped_workload,
        "skipped_in_progress": skipped_in_progress,
        "skipped_not_upgradeable": skipped_not_upgradeable,
        "skipped_proxy_bound": skipped_proxy_bound,
        "skipped_disk_full": skipped_disk_full,
        "missing_node_ids": missing,
        "max_concurrent": node_conf.LIFECYCLE_MAX_CONCURRENT,
    }


def enrich_node_row(*, org: Organization, node: Node, user=None) -> dict[str, Any]:
    """Read-only lifecycle/workload enrichment for console list (no side effects)."""
    lifecycle = None if node.is_deleted else compute_node_lifecycle(org=org, node=node)
    workload = None if node.is_deleted else node_workload_payload(node=node)
    return {
        "lifecycle": lifecycle,
        "workload": workload,
    }
