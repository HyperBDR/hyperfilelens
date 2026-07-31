from django.test import SimpleTestCase

from apps.lens_bridge.services.gateway_paths import (
    GatewayPathError,
    path_within_root,
)
from apps.lens_bridge.models import LensGatewayLink


class GatewayPathTests(SimpleTestCase):
    def test_gateway_default_mount_exposes_data_only(self):
        link = LensGatewayLink(organization_id=7)

        self.assertEqual(link.resolved_workspace_root(), "/workspace/org-7/data")

    def test_rejects_parent_traversal_before_normalization(self):
        with self.assertRaises(GatewayPathError):
            path_within_root(
                "/workspace/org-7/data/../../etc",
                "/workspace/org-7/data",
                allow_root=True,
            )

    def test_rejects_sibling_prefix(self):
        with self.assertRaises(GatewayPathError):
            path_within_root(
                "/workspace/org-7/database",
                "/workspace/org-7/data",
                allow_root=True,
            )

    def test_managed_workspace_must_be_strict_child(self):
        with self.assertRaises(GatewayPathError):
            path_within_root(
                "/workspace/org-7/data",
                "/workspace/org-7/data",
                allow_root=False,
            )

    def test_browse_may_use_root_itself(self):
        path = path_within_root(
            "/workspace/org-7/data/",
            "/workspace/org-7/data",
            allow_root=True,
        )
        self.assertEqual(path, "/workspace/org-7/data")
