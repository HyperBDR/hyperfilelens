"""
Control plane → Agent downlink using Channels ``group_send``.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.node.models import NodeTask
from apps.node.services.internal.agent_log import task_log_context
from apps.node.ws.groups import agent_group_name
from apps.node.ws.wire import task_cancel_wire, task_command_wire
from common.observability.context import get_request_id

CHANNEL_DOWNLINK_TYPE = "node.downlink"

logger = logging.getLogger(__name__)


def channel_downlink_event(message: dict[str, Any]) -> dict[str, Any]:
    """Channels event consumed by ``NodeAgentConsumer.node_downlink``."""
    return {"type": CHANNEL_DOWNLINK_TYPE, "message": message}


def send_task_command(*, task: NodeTask) -> None:
    trace_id = (get_request_id() or task.correlation_id or "").strip()
    wire = task_command_wire(
        task_id=task.id,
        kind=task.kind,
        node_id=task.node_id,
        payload=task.payload,
        correlation_type=task.correlation_type,
        correlation_id=task.correlation_id,
        trace_id=trace_id,
    )
    _fanout_downlink(node_id=task.node_id, wire=wire)


def send_task_cancel(*, task: NodeTask) -> None:
    wire = task_cancel_wire(task_id=task.id, node_id=task.node_id)
    _fanout_downlink(node_id=task.node_id, wire=wire)


def _fanout_downlink(*, node_id: int, wire: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.error(
            "agent downlink channel layer missing %s",
            task_log_context(
                node_id=node_id,
                task_id=str(wire.get("task_id") or ""),
                kind=str(wire.get("kind") or wire.get("type") or ""),
                trace_id=str(wire.get("trace_id") or ""),
            ),
        )
        raise RuntimeError("channel layer not configured")

    group = agent_group_name(node_id=node_id)
    event = channel_downlink_event(wire)
    logger.info(
        "agent downlink sending %s group=%s",
        task_log_context(
            node_id=node_id,
            task_id=str(wire.get("task_id") or ""),
            kind=str(wire.get("kind") or ""),
            trace_id=str(wire.get("trace_id") or ""),
        ),
        group,
    )
    async_to_sync(channel_layer.group_send)(group, event)
