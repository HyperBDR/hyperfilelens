from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class WebSocketRecoveryGateCommandTests(SimpleTestCase):
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
