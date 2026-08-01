from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.node.management.commands.ws_recovery_gate import Command
from apps.node.services.internal import redis_store


class WebSocketRecoveryGateCommandTests(SimpleTestCase):
    @patch("apps.node.services.internal.redis_store.get_redis")
    def test_agent_route_clear_uses_atomic_session_compare(self, get_redis):
        client = MagicMock()
        get_redis.return_value = client

        client.eval.return_value = 0
        self.assertFalse(
            redis_store.clear_agent_location_if_session(
                agent_id=7,
                session_id="drained-session",
            )
        )
        eval_args = client.eval.call_args.args
        self.assertEqual(eval_args[1:], (1, "agent_loc:7", "drained-session"))

        client.eval.return_value = 1
        self.assertTrue(
            redis_store.clear_agent_location_if_session(
                agent_id=7,
                session_id="current-session",
            )
        )

    @patch("apps.node.services.internal.redis_store.get_redis")
    def test_recovery_hold_is_owned_by_ws_instance(self, get_redis):
        client = MagicMock()
        get_redis.return_value = client
        with patch.object(redis_store.node_conf, "WS_INSTANCE_ID", "ws-blue-1"):
            self.assertTrue(redis_store.begin_ws_recovery_hold(seconds=30))
            self.assertTrue(redis_store.clear_ws_recovery_hold())

        client.set.assert_called_once_with(
            redis_store.ws_recovery_hold_key(),
            "ws-blue-1",
            ex=30,
        )
        eval_args = client.eval.call_args.args
        self.assertEqual(eval_args[1:], (1, "node_ws_recovery_hold", "ws-blue-1"))

    @patch("apps.node.management.commands.ws_recovery_gate.time.sleep")
    @patch(
        "apps.node.management.commands.ws_recovery_gate.redis_store.get_agent_location",
        side_effect=("old-ws", "new-ws"),
    )
    @patch("apps.node.management.commands.ws_recovery_gate.NodeTask.objects")
    def test_reattach_rejects_routes_owned_by_drained_instance(
        self, objects, get_location, sleep
    ):
        queryset = MagicMock()
        queryset.values_list.return_value.distinct.return_value = [7]
        objects.filter.return_value = queryset

        Command()._wait_for_active_task_nodes(
            timeout=5,
            excluded_instances={"old-ws"},
        )

        self.assertEqual(get_location.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("apps.node.management.commands.ws_recovery_gate.time.sleep")
    @patch("apps.node.management.commands.ws_recovery_gate.get_channel_layer")
    def test_drain_targets_only_the_current_ws_instance(self, channel_layer, sleep):
        group_send = AsyncMock()
        channel_layer.return_value = SimpleNamespace(group_send=group_send)

        call_command(
            "ws_recovery_gate",
            "drain",
            grace=0,
            stdout=StringIO(),
        )

        group_send.assert_awaited_once()
        group, event = group_send.await_args.args
        self.assertTrue(group.startswith("ws-instance."))
        self.assertEqual(event["type"], "deployment.drain")
        sleep.assert_called_once_with(0)

    @patch(
        "apps.node.management.commands.ws_recovery_gate.redis_store.begin_ws_recovery_hold",
        return_value=True,
    )
    def test_begin_sets_recovery_hold(self, begin_hold):
        call_command("ws_recovery_gate", "begin", stdout=StringIO())
        begin_hold.assert_called_once_with()

    @patch(
        "apps.node.management.commands.ws_recovery_gate.redis_store.clear_ws_recovery_hold",
        return_value=True,
    )
    @patch(
        "apps.node.management.commands.ws_recovery_gate.Command._ready",
        return_value=True,
    )
    def test_complete_clears_hold_after_route_is_ready(self, _ready, clear_hold):
        call_command(
            "ws_recovery_gate",
            "complete",
            timeout=1,
            stdout=StringIO(),
        )
        clear_hold.assert_called_once_with()

    @patch(
        "apps.node.management.commands.ws_recovery_gate.Command._ready",
        return_value=False,
    )
    def test_check_fails_when_route_is_not_ready(self, _ready):
        with self.assertRaises(CommandError):
            call_command("ws_recovery_gate", "check", stderr=StringIO())
