"""Tests for Agent uplink Redis stream ingest."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.iam.models import Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.ws.uplink_queue import (
    NODE_UPLINK_STREAM,
    UPLINK_INGEST_GROUP,
    drain_uplink_stream,
    enqueue_uplink,
    touch_heartbeat_fast,
)
from apps.node.ws.wire import ParsedUplink, WireType


class _StreamRedis:
    def __init__(self) -> None:
        self.groups: set[tuple[str, str]] = set()
        self.stream: list[tuple[str, dict[str, str]]] = []
        self.acked: set[str] = set()
        self._seq = 0

    def ping(self) -> bool:
        return True

    def xgroup_create(self, name, groupname, id="0", mkstream=False):
        key = (name, groupname)
        if key in self.groups:
            from redis.exceptions import ResponseError

            raise ResponseError("BUSYGROUP Consumer Group name already exists")
        self.groups.add(key)

    def xadd(self, name, fields):
        self._seq += 1
        entry_id = f"{self._seq}-0"
        self.stream.append((entry_id, dict(fields)))
        return entry_id

    def xreadgroup(self, group, consumer, streams, count=10, block=0):
        stream_name = next(iter(streams))
        pending = [
            (entry_id, fields)
            for entry_id, fields in self.stream
            if entry_id not in self.acked
        ][:count]
        if not pending:
            return []
        return [(stream_name, pending)]

    def xack(self, stream, group, entry_id):
        self.acked.add(entry_id)


class UplinkQueueTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="uplink-org", name="Uplink Org")
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-uplink",
            role=NodeRole.AGENT,
            status=Node.Status.OFFLINE,
            last_seen_at=timezone.now(),
        )
        self.redis = _StreamRedis()
        self._patch = patch(
            "apps.node.ws.uplink_queue._redis",
            return_value=self.redis,
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)

    @patch("apps.node.ws.uplink_queue.redis_store.ensure_agent_location_on_heartbeat")
    @patch("apps.node.ws.uplink_queue.redis_store.touch_ws_instance_alive")
    def test_touch_heartbeat_fast_only_touches_redis(self, mock_alive, mock_ensure):
        touch_heartbeat_fast(node_id=self.node.id, session_id="session-1")
        mock_ensure.assert_called_once_with(
            agent_id=self.node.id,
            session_id="session-1",
        )
        mock_alive.assert_called_once()

    @patch("apps.node.ws.uplink.handle_uplink")
    def test_drain_uplink_stream_processes_heartbeat(self, mock_handle):
        message = ParsedUplink(msg_type=WireType.HEARTBEAT, heartbeat_payload={"agent_version": "1.0.0"})
        enqueue_uplink(node_id=self.node.id, message=message)
        processed = drain_uplink_stream(count=10)
        self.assertEqual(processed, 1)
        mock_handle.assert_called_once()
        self.assertEqual(mock_handle.call_args.kwargs["node_id"], self.node.id)

    def test_stream_constants(self):
        self.assertEqual(NODE_UPLINK_STREAM, "node:uplink:stream")
        self.assertEqual(UPLINK_INGEST_GROUP, "node-uplink-ingest")
