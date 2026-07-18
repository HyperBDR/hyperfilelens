"""
Agent removal: optional WSS uninstall, then always purge SaaS-side records.

When the agent is routable over WebSocket, dispatch ``agent.uninstall`` and wait
briefly (default 15s) for detached task.result. Agent disconnect or task failure
during uninstall must not block server-side cleanup.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.audit.constants import AuditAction, AuditResult
from apps.audit.services.interface import write_audit_log
from apps.iam.models import Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal import redis_store
from apps.node.services.internal.agent_task import (
    run_agent_task_async,
    wait_for_agent_task,
)
from apps.node.services.internal.node_registry import agent_ws_routable
from apps.source.models import SourceResource

logger = logging.getLogger(__name__)


class ProxyHasBoundResources(RuntimeError):
    """Raised when removing a Proxy that still has bound resources."""

    def __init__(self, bindings) -> None:
        self.bindings = bindings
        super().__init__("Proxy has bound resources.")


_DEFAULT_UNINSTALL_WAIT_SECONDS = 15


_MANAGED_NODE_ROLES = frozenset({NodeRole.AGENT, NodeRole.PROXY, NodeRole.GATEWAY})


def remove_agent_node(
    *,
    org: Organization,
    node: Node,
    user=None,
    keep_data: bool = False,
    wait_timeout_seconds: int = _DEFAULT_UNINSTALL_WAIT_SECONDS,
) -> dict[str, Any]:
    """
    Remove an enrolled node (agent, proxy, or gateway) from the control plane.

    - Online (WSS routable): dispatch ``agent.uninstall`` with ``keep_data`` (default purge host data).
    - Offline: skip agent contact.
    - Always: soft-delete bound source resources and the node row.
    """
    if node.role not in _MANAGED_NODE_ROLES:
        raise ValueError("remove_agent_node applies to agent/proxy/gateway roles only")
    if node.organization_id != org.id:
        raise ValueError("node/org mismatch")

    if node.role == NodeRole.PROXY:
        # A Proxy can only be removed when it has no bound resources.
        from apps.node.services.internal.bindings import (
            collect_proxy_bindings,
        )

        bindings = collect_proxy_bindings(
            organization_id=org.id,
            proxy_id=node.id,
        )
        if not bindings.is_empty():
            raise ProxyHasBoundResources(bindings)

    uninstall_attempted = False
    uninstall_task_status: str | None = None
    timed_out = False

    if agent_ws_routable(agent_id=node.id):
        uninstall_attempted = True
        try:
            handle = run_agent_task_async(
                org=org,
                node_id=node.id,
                kind="agent.uninstall",
                payload={"keep_data": keep_data},
                correlation_type="agent.uninstall",
                correlation_id=str(node.id),
            )
            outcome = wait_for_agent_task(
                task_id=handle.task_id,
                timeout_seconds=max(15, int(wait_timeout_seconds)),
            )
            uninstall_task_status = outcome.task.status
            timed_out = outcome.timed_out
            logger.info(
                "agent uninstall finished node_id=%s status=%s timed_out=%s",
                node.id,
                uninstall_task_status,
                timed_out,
            )
        except Exception as exc:
            logger.warning(
                "agent uninstall dispatch/wait failed node_id=%s: %s",
                node.id,
                exc,
                exc_info=True,
            )
            uninstall_task_status = "error"

    summary = _purge_agent_server_records(org=org, node=node, user=user)
    summary.update(
        {
            "node_id": node.id,
            "uninstall_attempted": uninstall_attempted,
            "uninstall_task_status": uninstall_task_status,
            "uninstall_timed_out": timed_out,
        }
    )
    return summary


def remove_agent_node_for_source_resource(
    *,
    resource: SourceResource,
    user=None,
    keep_data: bool = False,
    wait_timeout_seconds: int = _DEFAULT_UNINSTALL_WAIT_SECONDS,
) -> dict[str, Any] | None:
    """When a local source host is backed by an Agent, remove the whole agent."""
    if resource.resource_type != "local":
        return None

    node = resource.bound_node
    if node is None and resource.bound_node_id:
        node = Node.objects.filter(
            pk=resource.bound_node_id,
            organization_id=resource.organization_id,
            is_deleted=False,
        ).first()
    if node is None or node.role != NodeRole.AGENT:
        return None
    return remove_agent_node(
        org=resource.organization,
        node=node,
        user=user,
        keep_data=keep_data,
        wait_timeout_seconds=wait_timeout_seconds,
    )


@transaction.atomic
def _purge_agent_server_records(
    *,
    org: Organization,
    node: Node,
    user,
) -> dict[str, Any]:
    from apps.protection.services.backup_config import purge_backup_config_data_for_source
    from apps.source.services.internal.source_pipeline import delete_pipeline_entry

    resources_removed = 0
    for resource in SourceResource.objects.filter(
        organization_id=org.id,
        bound_node=node,
        is_deleted=False,
    ):
        write_audit_log(
            organization=org,
            user=user,
            action=AuditAction.DELETE,
            resource_type="source_resource",
            resource_id=str(resource.id),
            resource_name=resource.name,
            result=AuditResult.SUCCESS,
            metadata={"reason": "agent_removed", "node_id": node.id},
        )
        resource.soft_delete()
        resources_removed += 1

    redis_store.clear_agent_location(agent_id=node.id)
    if node.role == NodeRole.GATEWAY:
        _purge_gateway_lens_records(org=org, gateway=node, user=user)

    backup_cleanup = purge_backup_config_data_for_source(
        organization_id=org.id,
        source_type="agent",
        source_ref_id=node.id,
    )
    delete_pipeline_entry(
        organization_id=org.id,
        source_kind="agent",
        ref_id=node.id,
    )

    write_audit_log(
        organization=org,
        user=user,
        action=AuditAction.DELETE,
        resource_type="node",
        resource_id=str(node.id),
        resource_name=node.name,
        result=AuditResult.SUCCESS,
        metadata={"role": node.role, "reason": "agent_removed"},
    )
    node.soft_delete()

    return {
        "resources_removed": resources_removed,
        "server_records_purged": True,
        **backup_cleanup,
    }


def _purge_gateway_lens_records(*, org: Organization, gateway: Node, user) -> None:
    from apps.lens_bridge.models import LensGatewayLink, LensKnowledgeSource

    ks_removed = 0
    for ks in LensKnowledgeSource.objects.filter(
        organization_id=org.id,
        gateway=gateway,
        is_deleted=False,
    ):
        write_audit_log(
            organization=org,
            user=user,
            action=AuditAction.DELETE,
            resource_type="lens_knowledge_source",
            resource_id=str(ks.id),
            resource_name=ks.name,
            result=AuditResult.SUCCESS,
            metadata={"reason": "gateway_removed", "gateway_id": gateway.id},
        )
        ks.soft_delete()
        ks_removed += 1

    for link in LensGatewayLink.objects.filter(
        organization_id=org.id,
        gateway=gateway,
        is_deleted=False,
    ):
        link.sidecar_status = LensGatewayLink.SidecarStatus.NOT_DEPLOYED
        config = dict(link.config_json or {})
        config["lifecycle_status"] = "removed"
        link.config_json = config
        link.soft_delete()
