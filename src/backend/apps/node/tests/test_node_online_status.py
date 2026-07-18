"""Agent node online/offline follows WebSocket session lifecycle."""

from __future__ import annotations

import json

from django.test import TestCase
from django.utils import timezone

from apps.iam.models import Organization
from apps.node import conf as node_conf
from apps.node.models import Node, NodeTask
from apps.node.models.base import NodeRole
from apps.node.services.internal import redis_store
from apps.node.services.internal.node_registry import (
    CONNECTION_RECONNECTING,
    agent_connection_status,
    effective_agent_node_status,
    reconcile_stale_online_nodes,
)
from apps.node.ws.uplink import on_agent_connected, on_agent_disconnected


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def ping(self) -> bool:
        return True

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.data:
                deleted += 1
                self.data.pop(key, None)
        return deleted

    def exists(self, key: str) -> bool:
        return key in self.data

    def expire(self, key: str, ex: int) -> None:
        return None

    def scan_iter(self, match: str = "*", count: int = 10):
        prefix = match[:-1] if match.endswith("*") else match
        for key in list(self.data):
            if match == "*" or key.startswith(prefix):
                yield key


class AgentNodeOnlineStatusTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="node-status-org", name="Node Status Org")
        self.node = Node.objects.create(
            organization=self.org,
            name="agent-1",
            role=NodeRole.AGENT,
            status=Node.Status.OFFLINE,
        )
        self.redis = _FakeRedis()
        self._redis_patcher = self._patch_redis(self.redis)
        self._redis_patcher.start()
        self.addCleanup(self._redis_patcher.stop)
        redis_store._client = None
        from unittest.mock import patch

        self._lifecycle_delay = patch(
            "apps.node.tasks.lifecycle.advance_node_lifecycle_for_node.delay",
        )
        self._lifecycle_delay.start()
        self.addCleanup(self._lifecycle_delay.stop)

    @staticmethod
    def _patch_redis(fake: _FakeRedis):
        from unittest.mock import patch

        return patch(
            "apps.node.services.internal.redis_store.get_redis",
            return_value=fake,
        )

    def _mark_ws_alive(self) -> None:
        ws_id = node_conf.WS_INSTANCE_ID
        self.redis.set(redis_store.ws_alive_key(ws_id), "1")

    def test_ws_connect_marks_online(self):
        self._mark_ws_alive()
        on_agent_connected(node_id=self.node.id, session_id="session-a")

        self.node.refresh_from_db()
        self.assertEqual(self.node.status, Node.Status.ONLINE)
        self.assertEqual(
            effective_agent_node_status(self.node),
            Node.Status.ONLINE,
        )

    def test_ws_disconnect_enters_reconnecting_grace(self):
        self._mark_ws_alive()
        on_agent_connected(node_id=self.node.id, session_id="session-a")
        on_agent_disconnected(node_id=self.node.id, session_id="session-a")

        self.node.refresh_from_db()
        self.assertEqual(self.node.status, Node.Status.ONLINE)
        self.assertEqual(agent_connection_status(self.node), CONNECTION_RECONNECTING)
        self.assertIsNone(redis_store.get_agent_location(agent_id=self.node.id))
        self.assertEqual(
            effective_agent_node_status(self.node),
            Node.Status.ONLINE,
        )

    def test_ws_disconnect_effective_offline_after_grace(self):
        self._mark_ws_alive()
        on_agent_connected(node_id=self.node.id, session_id="session-a")
        on_agent_disconnected(node_id=self.node.id, session_id="session-a")

        stale_at = timezone.now() - timezone.timedelta(
            seconds=node_conf.AGENT_LOC_TTL_SECONDS + 5,
        )
        Node.objects.filter(pk=self.node.id).update(last_seen_at=stale_at)
        self.node.refresh_from_db()

        self.assertEqual(
            effective_agent_node_status(self.node),
            Node.Status.OFFLINE,
        )

    def test_ws_disconnect_does_not_fail_active_task(self):
        self._mark_ws_alive()
        on_agent_connected(node_id=self.node.id, session_id="session-a")
        task = NodeTask.objects.create(
            organization=self.org,
            node=self.node,
            kind="repo.status",
            status=NodeTask.Status.RUNNING,
            watchdog_deadline_at=timezone.now(),
        )

        on_agent_disconnected(node_id=self.node.id, session_id="session-a")

        task.refresh_from_db()
        self.assertEqual(task.status, NodeTask.Status.RUNNING)
        self.assertEqual(task.last_error, "")

    def test_stale_disconnect_after_reconnect_stays_online(self):
        self._mark_ws_alive()
        on_agent_connected(node_id=self.node.id, session_id="session-a")
        on_agent_connected(node_id=self.node.id, session_id="session-b")
        on_agent_disconnected(node_id=self.node.id, session_id="session-a")

        self.node.refresh_from_db()
        self.assertEqual(self.node.status, Node.Status.ONLINE)
        self.assertEqual(
            effective_agent_node_status(self.node),
            Node.Status.ONLINE,
        )

    def test_effective_status_offline_without_ws_route(self):
        self.node.status = Node.Status.ONLINE
        self.node.last_seen_at = timezone.now() - timezone.timedelta(
            seconds=node_conf.AGENT_LOC_TTL_SECONDS + 5,
        )
        self.node.save(update_fields=["status", "last_seen_at", "updated_at"])

        self.assertEqual(
            effective_agent_node_status(self.node),
            Node.Status.OFFLINE,
        )
        self.assertEqual(agent_connection_status(self.node), Node.Status.OFFLINE)

    def test_effective_status_grace_without_ws_route(self):
        self.node.status = Node.Status.ONLINE
        self.node.last_seen_at = timezone.now()
        self.node.save(update_fields=["status", "last_seen_at", "updated_at"])

        self.assertEqual(
            effective_agent_node_status(self.node),
            Node.Status.ONLINE,
        )

    def test_reconcile_marks_stale_online_offline(self):
        self._mark_ws_alive()
        on_agent_connected(node_id=self.node.id, session_id="session-a")
        self.redis.delete(redis_store.agent_loc_key(self.node.id))
        stale_at = timezone.now() - timezone.timedelta(
            seconds=node_conf.AGENT_LOC_TTL_SECONDS + 5,
        )
        Node.objects.filter(pk=self.node.id).update(last_seen_at=stale_at)

        summary = reconcile_stale_online_nodes(limit=10)

        self.node.refresh_from_db()
        self.assertEqual(self.node.status, Node.Status.OFFLINE)
        self.assertEqual(summary["nodes_marked_offline"], 1)

    def test_reconcile_skips_recent_last_seen(self):
        self._mark_ws_alive()
        on_agent_connected(node_id=self.node.id, session_id="session-a")
        self.redis.delete(redis_store.agent_loc_key(self.node.id))

        summary = reconcile_stale_online_nodes(limit=10)

        self.node.refresh_from_db()
        self.assertEqual(self.node.status, Node.Status.ONLINE)
        self.assertEqual(summary["nodes_marked_offline"], 0)

    def test_legacy_plain_agent_loc_value_still_routable(self):
        ws_id = node_conf.WS_INSTANCE_ID
        self.redis.set(redis_store.agent_loc_key(self.node.id), ws_id)
        self._mark_ws_alive()

        self.assertEqual(redis_store.get_agent_location(agent_id=self.node.id), ws_id)

        self.node.status = Node.Status.ONLINE
        self.node.save(update_fields=["status", "updated_at"])
        self.assertEqual(
            effective_agent_node_status(self.node),
            Node.Status.ONLINE,
        )
        self.assertEqual(agent_connection_status(self.node), Node.Status.ONLINE)

    def test_connection_status_online_when_agent_loc_present_without_ws_alive(self):
        """Other agents must not show reconnecting when only shared ws_alive flickers."""
        ws_id = node_conf.WS_INSTANCE_ID
        redis_store.set_agent_location(
            agent_id=self.node.id,
            session_id="session-z",
            ws_instance_id=ws_id,
        )
        self.node.status = Node.Status.ONLINE
        self.node.last_seen_at = timezone.now()
        self.node.save(update_fields=["status", "last_seen_at", "updated_at"])

        self.assertFalse(redis_store.get_redis().exists(redis_store.ws_alive_key(ws_id)))
        self.assertEqual(agent_connection_status(self.node), Node.Status.ONLINE)

    def test_session_payload_round_trip(self):
        ws_id = node_conf.WS_INSTANCE_ID
        redis_store.set_agent_location(
            agent_id=self.node.id,
            session_id="session-x",
            ws_instance_id=ws_id,
        )
        raw = self.redis.get(redis_store.agent_loc_key(self.node.id))
        assert raw is not None
        payload = json.loads(raw)
        self.assertEqual(payload["ws"], ws_id)
        self.assertEqual(payload["session"], "session-x")

    def test_clear_ws_instance_routes_only_current_instance(self):
        ws_id = node_conf.WS_INSTANCE_ID
        other_ws = "other-ws"
        redis_store.set_agent_location(
            agent_id=self.node.id,
            session_id="session-x",
            ws_instance_id=ws_id,
        )
        other_node = Node.objects.create(
            organization=self.org,
            name="agent-2",
            role=NodeRole.AGENT,
            status=Node.Status.ONLINE,
        )
        redis_store.set_agent_location(
            agent_id=other_node.id,
            session_id="session-y",
            ws_instance_id=other_ws,
        )
        self.redis.set(redis_store.ws_alive_key(ws_id), "1")
        self.redis.set(redis_store.ws_alive_key(other_ws), "1")

        summary = redis_store.clear_ws_instance_routes(ws_instance_id=ws_id)

        self.assertEqual(summary["agent_locations_deleted"], 1)
        self.assertEqual(summary["ws_alive_deleted"], 1)
        self.assertIsNone(redis_store.get_agent_location(agent_id=self.node.id))
        self.assertEqual(redis_store.get_agent_location(agent_id=other_node.id), other_ws)
        self.assertTrue(self.redis.exists(redis_store.ws_alive_key(other_ws)))

    def test_ttl_defaults_exceed_agent_heartbeat_interval(self):
        """Prevent online/offline flicker between 30s WSS heartbeats."""
        heartbeat_seconds = 30
        self.assertGreater(
            node_conf.WS_INSTANCE_ALIVE_TTL_SECONDS,
            heartbeat_seconds,
        )
        self.assertGreater(
            node_conf.AGENT_LOC_TTL_SECONDS,
            heartbeat_seconds,
        )

    def test_ensure_agent_location_on_heartbeat_recreates_expired_lease(self):
        ws_id = node_conf.WS_INSTANCE_ID
        self.node.status = Node.Status.ONLINE
        self.node.last_seen_at = timezone.now()
        self.node.save(update_fields=["status", "last_seen_at", "updated_at"])
        redis_store.set_agent_location(
            agent_id=self.node.id,
            session_id="session-old",
            ws_instance_id=ws_id,
        )
        self.redis.delete(redis_store.agent_loc_key(self.node.id))
        self.assertFalse(self.redis.exists(redis_store.agent_loc_key(self.node.id)))

        redis_store.ensure_agent_location_on_heartbeat(
            agent_id=self.node.id,
            session_id="session-live",
        )

        self.assertTrue(self.redis.exists(redis_store.agent_loc_key(self.node.id)))
        raw = self.redis.get(redis_store.agent_loc_key(self.node.id))
        payload = json.loads(raw)
        self.assertEqual(payload["session"], "session-live")
        self.assertEqual(agent_connection_status(self.node), Node.Status.ONLINE)
