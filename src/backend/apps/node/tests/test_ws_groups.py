"""Channels group naming for Agent WebSocket."""

from django.test import SimpleTestCase

from apps.node.ws.groups import agent_group_name


class AgentGroupNameTests(SimpleTestCase):
    def test_valid_for_channels_redis(self):
        name = agent_group_name(node_id=2)
        self.assertEqual(name, "agent.2")
        self.assertNotIn(":", name)
