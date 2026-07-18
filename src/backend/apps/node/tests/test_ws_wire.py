"""WebSocket wire parsing (control plane ↔ Agent)."""

from django.test import SimpleTestCase

from apps.node.ws.wire import (
    ParsedUplink,
    WireType,
    heartbeat_ack_wire,
    loads_json,
    parse_uplink,
    task_command_wire,
)


class WireParseTests(SimpleTestCase):
    def test_heartbeat(self):
        msg = parse_uplink({"type": "heartbeat"})
        self.assertIsInstance(msg, ParsedUplink)
        self.assertEqual(msg.msg_type, WireType.HEARTBEAT)

    def test_task_progress(self):
        msg = parse_uplink(
            {
                "type": "task.progress",
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "progress": {"pct": 50},
            }
        )
        self.assertIsInstance(msg, ParsedUplink)
        self.assertEqual(msg.msg_type, WireType.TASK_PROGRESS)
        self.assertEqual(msg.progress, {"pct": 50})

    def test_invalid_json(self):
        self.assertIsNone(loads_json("not-json"))

    def test_unknown_type_returns_none(self):
        self.assertIsNone(parse_uplink({"type": "task.complete"}))

    def test_task_command_wire(self):
        body = task_command_wire(
            task_id="550e8400-e29b-41d4-a716-446655440000",
            kind="browse",
            node_id=1,
            payload={"path": "/"},
        )
        self.assertEqual(body["type"], WireType.TASK_COMMAND)
        self.assertEqual(body["node_id"], 1)

    def test_heartbeat_ack_wire(self):
        body = heartbeat_ack_wire()
        self.assertEqual(body["type"], WireType.HEARTBEAT_ACK)
