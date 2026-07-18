"""
Node registry reconciliation for stale heartbeats and WebSocket instance loss.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node import conf as node_conf
from apps.node.services.internal import redis_store
from apps.node.services.internal.task import fail_active_tasks_for_node

logger = logging.getLogger(__name__)

CONNECTION_ONLINE = Node.Status.ONLINE
CONNECTION_RECONNECTING = "reconnecting"
CONNECTION_OFFLINE = Node.Status.OFFLINE


def _agent_lease_grace_seconds() -> int:
    return node_conf.AGENT_LOC_TTL_SECONDS


def _last_seen_within_grace(node: Node) -> bool:
    if not node.last_seen_at:
        return False
    grace = timezone.timedelta(seconds=_agent_lease_grace_seconds())
    return timezone.now() - node.last_seen_at < grace


def effective_agent_node_status(node: Node) -> str:
    """
    Agent / Proxy nodes are online only when DB status is online and Redis has a live WSS session.
    """
    if node.role not in (NodeRole.AGENT, NodeRole.PROXY):
        return node.status
    if node.status != Node.Status.ONLINE:
        return Node.Status.OFFLINE
    if _agent_routable(agent_id=node.id):
        return Node.Status.ONLINE
    if _last_seen_within_grace(node):
        return Node.Status.ONLINE
    return Node.Status.OFFLINE


def agent_connection_status(node: Node) -> str:
    """
    Display-oriented connectivity state.

    ``online`` means the agent still holds a live WSS lease (``agent_loc``) or is
    fully routable. ``reconnecting`` means the lease was cleared but ``last_seen_at``
    is still within grace (expected during agent restarts). Shared ``node_alive:*``
    keys are *not* used here — a flicker on one WS worker must not mark unrelated
    agents as reconnecting while their own ``agent_loc`` is still refreshed.
    """
    if node.role not in (NodeRole.AGENT, NodeRole.PROXY):
        return node.status
    if node.status != Node.Status.ONLINE:
        return CONNECTION_OFFLINE
    if agent_ws_routable(agent_id=node.id):
        return CONNECTION_ONLINE
    if _agent_loc_key_exists(agent_id=node.id):
        return CONNECTION_ONLINE
    if _last_seen_within_grace(node):
        return CONNECTION_RECONNECTING
    return CONNECTION_OFFLINE


def _within_reconnect_grace(node: Node) -> bool:
    return _last_seen_within_grace(node)


def _agent_loc_key_exists(*, agent_id: int) -> bool:
    """True when Redis still holds an ``agent_loc`` lease for this agent."""
    r = redis_store.get_redis()
    if r is None:
        return True
    return bool(r.exists(redis_store.agent_loc_key(agent_id)))


def agent_session_registered(*, agent_id: int) -> bool:
    """True when the agent has an active WSS session lease (``agent_loc`` key present)."""
    return _agent_loc_key_exists(agent_id=agent_id)


def agent_ws_routable(*, agent_id: int) -> bool:
    """True when the agent has a live WebSocket session in Redis (``agent_loc`` + ws alive)."""
    return _agent_routable(agent_id=agent_id)


def _agent_routable(*, agent_id: int) -> bool:
    ws_instance = redis_store.get_agent_location(agent_id=agent_id)
    if not ws_instance:
        return False
    client = redis_store.get_redis()
    if client is None:
        return True
    return bool(client.exists(redis_store.ws_alive_key(ws_instance)))


def reconcile_stale_online_nodes(*, limit: int = 200) -> dict[str, int]:
    """
    Mark ``online`` nodes without fresh Redis routing as ``offline``.

    Fails in-flight ``NodeTask`` rows on affected nodes (ghost-task cleanup).
    """
    nodes_marked_offline = 0
    tasks_failed = 0

    node_ids = list(
        Node.objects.filter(status=Node.Status.ONLINE)
        .order_by("last_seen_at", "id")
        .values_list("pk", flat=True)[: max(1, int(limit))]
    )

    for node_id in node_ids:
        with transaction.atomic():
            node = (
                Node.objects.select_for_update()
                .filter(pk=node_id, status=Node.Status.ONLINE)
                .first()
            )
            if node is None:
                continue
            if _agent_routable(agent_id=node.id):
                continue
            if _last_seen_within_grace(node):
                continue

            node.status = Node.Status.OFFLINE
            node.save(update_fields=["status", "updated_at"])
            nodes_marked_offline += 1
            try:
                from apps.source.services.internal.agent_host_sync import sync_agent_source_host

                sync_agent_source_host(node=node)
            except Exception:
                logger.debug("agent source-host sync failed node_id=%s", node.id, exc_info=True)

            failed = fail_active_tasks_for_node(
                node_id=node.id,
                reason="agent heartbeat expired (registry reconcile)",
            )
            tasks_failed += failed
            logger.info(
                "node %s marked offline (stale agent_loc); failed_tasks=%s",
                node.id,
                failed,
            )

    return {
        "nodes_marked_offline": nodes_marked_offline,
        "tasks_failed": tasks_failed,
        "checked_at": timezone.now().isoformat(),
    }
