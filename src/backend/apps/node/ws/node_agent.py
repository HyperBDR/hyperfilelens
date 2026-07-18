"""
``NodeAgentConsumer`` — Agent WSS session at ``/ws/node/agent/``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.node.services.internal.agent_ws_auth import validate_agent_ws_credentials
from apps.node.services.internal.client_ip import resolve_agent_client_ip_from_scope
from apps.node.ws.groups import agent_group_name
from apps.node.ws.uplink import handle_uplink, on_agent_connected, on_agent_disconnected, apply_heartbeat_inventory_snapshot
from apps.node.ws.uplink_queue import enqueue_uplink, touch_heartbeat_fast
from apps.node.ws.wire import WireType, dumps_wire, heartbeat_ack_wire, loads_json, parse_uplink

logger = logging.getLogger(__name__)

_CLOSE_UNAUTHORIZED = 4401


@dataclass(frozen=True)
class _ConnectParams:
    node_id: int
    token: str


def _parse_connect_params(scope: dict) -> _ConnectParams | None:
    raw = (scope.get("query_string") or b"").decode("utf-8")
    qs = parse_qs(raw)
    node_raw = (qs.get("node_id") or qs.get("agent_id") or [""])[0].strip()
    token = (qs.get("token") or [""])[0].strip()
    if not node_raw.isdigit() or not token:
        return None
    return _ConnectParams(node_id=int(node_raw), token=token)


class NodeAgentConsumer(AsyncWebsocketConsumer):
    """Handle registry heartbeats and ``NodeTask`` uplink frames."""

    node_id: int
    agent_group: str

    async def connect(self) -> None:
        params = _parse_connect_params(self.scope)
        if params is None:
            logger.warning("agent ws connect rejected: missing node_id or token")
            await self.close(code=_CLOSE_UNAUTHORIZED)
            return

        ok = await database_sync_to_async(validate_agent_ws_credentials)(
            params.node_id,
            params.token,
        )
        if not ok:
            logger.warning("agent ws connect rejected: invalid credentials node_id=%s", params.node_id)
            await self.close(code=_CLOSE_UNAUTHORIZED)
            return

        self.node_id = params.node_id
        self.session_id = uuid.uuid4().hex
        self.agent_group = agent_group_name(node_id=self.node_id)
        await self.channel_layer.group_add(self.agent_group, self.channel_name)
        await self.accept()
        await database_sync_to_async(on_agent_connected)(
            node_id=self.node_id,
            session_id=self.session_id,
            client_ip=resolve_agent_client_ip_from_scope(self.scope),
        )

    async def disconnect(self, close_code: int) -> None:
        if getattr(self, "agent_group", ""):
            await self.channel_layer.group_discard(
                self.agent_group,
                self.channel_name,
            )
        if getattr(self, "node_id", None) and getattr(self, "session_id", ""):
            await database_sync_to_async(on_agent_disconnected)(
                node_id=self.node_id,
                session_id=self.session_id,
            )

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        if text_data is None and bytes_data is not None:
            text_data = bytes_data.decode("utf-8", errors="replace")
        if not text_data:
            return

        data = loads_json(text_data)
        if data is None:
            logger.debug("ignored non-json frame node_id=%s", self.node_id)
            return

        message = parse_uplink(data)
        if message is None:
            logger.debug("ignored unknown uplink type node_id=%s", self.node_id)
            return

        if message.msg_type == WireType.HEARTBEAT:
            await database_sync_to_async(touch_heartbeat_fast)(
                node_id=self.node_id,
                session_id=self.session_id,
            )
            await self.send(text_data=dumps_wire(heartbeat_ack_wire()))
            await database_sync_to_async(apply_heartbeat_inventory_snapshot)(
                node_id=self.node_id,
                inventory=message.heartbeat_payload,
            )
            await database_sync_to_async(enqueue_uplink)(node_id=self.node_id, message=message)
            return

        # Task frames drive watchdog + lifecycle; must persist synchronously.
        await database_sync_to_async(handle_uplink)(
            node_id=self.node_id,
            message=message,
        )

    async def node_downlink(self, event: dict) -> None:
        """Deliver a flat downlink frame (``task.command`` / ``task.cancel``)."""
        body = event.get("message")
        if not isinstance(body, dict):
            return
        try:
            await self.send(text_data=dumps_wire(body))
        except Exception:
            logger.warning(
                "agent downlink send failed node_id=%s task_id=%s kind=%s",
                getattr(self, "node_id", "-"),
                body.get("task_id"),
                body.get("kind"),
                exc_info=True,
            )
