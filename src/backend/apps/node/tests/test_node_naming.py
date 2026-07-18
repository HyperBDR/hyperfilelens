"""Tests for default node naming on enrollment."""

from django.test import SimpleTestCase

from apps.node.services.internal.node_naming import (
    hostname_from_metadata,
    is_auto_assigned_node_name,
    resolve_registration_node_name,
)


class NodeNamingTests(SimpleTestCase):
    def test_hostname_from_inventory(self):
        meta = {"inventory": {"hostname": "host-a"}}
        self.assertEqual(hostname_from_metadata(meta), "host-a")

    def test_hostname_from_metadata_root(self):
        meta = {"hostname": "host-b"}
        self.assertEqual(hostname_from_metadata(meta), "host-b")

    def test_resolve_registration_prefers_hostname(self):
        name = resolve_registration_node_name(
            payload={
                "name": "new-node",
                "metadata": {"hostname": "proxy-gw-01"},
            },
        )
        self.assertEqual(name, "proxy-gw-01")

    def test_resolve_registration_keeps_custom_name(self):
        name = resolve_registration_node_name(
            payload={
                "name": "custom-label",
                "metadata": {},
            },
        )
        self.assertEqual(name, "custom-label")

    def test_auto_assigned_names(self):
        self.assertTrue(is_auto_assigned_node_name("new-node"))
        self.assertTrue(is_auto_assigned_node_name(""))
        self.assertFalse(is_auto_assigned_node_name("proxy-gw-01"))
