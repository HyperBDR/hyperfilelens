"""Tests for manual replay of quarantined Agent uplink messages."""

from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase


class ReplayUplinkDeadLettersCommandTests(SimpleTestCase):
    @patch(
        "apps.node.management.commands.replay_uplink_dead_letters."
        "replay_dead_letter_entry",
        return_value="2-0",
    )
    @patch(
        "apps.node.management.commands.replay_uplink_dead_letters."
        "redis_store.get_redis"
    )
    def test_replays_selected_entry(self, get_redis, replay) -> None:
        client = Mock()
        client.xrange.return_value = [
            (
                "1-0",
                {"source_entry_id": "old-0", "payload": '{"node_id":1}'},
            )
        ]
        get_redis.return_value = client
        stdout = StringIO()

        call_command(
            "replay_uplink_dead_letters",
            "--entry-id",
            "1-0",
            stdout=stdout,
        )

        replay.assert_called_once_with(
            client,
            entry_id="1-0",
            fields={"source_entry_id": "old-0", "payload": '{"node_id":1}'},
        )
        self.assertIn("replayed 1-0 as 2-0", stdout.getvalue())

    @patch(
        "apps.node.management.commands.replay_uplink_dead_letters."
        "replay_dead_letter_entry"
    )
    @patch(
        "apps.node.management.commands.replay_uplink_dead_letters."
        "redis_store.get_redis"
    )
    def test_dry_run_does_not_replay(self, get_redis, replay) -> None:
        client = Mock()
        client.xrange.return_value = [
            ("1-0", {"source_entry_id": "old-0", "payload": "payload"})
        ]
        get_redis.return_value = client
        stdout = StringIO()

        call_command(
            "replay_uplink_dead_letters",
            "--dry-run",
            stdout=stdout,
        )

        replay.assert_not_called()
        self.assertIn("would replay 1-0", stdout.getvalue())
