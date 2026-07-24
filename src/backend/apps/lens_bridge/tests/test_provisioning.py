from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.lens_bridge.services import sl_client
from apps.lens_bridge.services.provisioning import _lensnode_dir_paths


class SlClientErrorFormatTests(SimpleTestCase):
    def test_format_non_field_errors(self):
        body = {"non_field_errors": ["selected_dirs path is not available on LensNode: /x"]}
        self.assertIn("selected_dirs", sl_client._format_sl_error(body))

    def test_format_field_errors(self):
        body = {"name": ["This field is required."]}
        self.assertIn("name", sl_client._format_sl_error(body))


class BuildLensEnrollConfigTests(SimpleTestCase):
    @patch(
        "apps.lens_bridge.deploy.local_platform_lens_gateway_base_url",
        return_value="https://127.0.0.1:11443/sourcelens",
    )
    @patch(
        "apps.lens_bridge.deploy.lens_gateway_base_url",
        return_value="https://console.example/sourcelens",
    )
    def test_installer_managed_gateway_gets_local_lens_url(
        self, _public_url, _local_url
    ):
        from apps.lens_bridge.services.provisioning import build_lens_enroll_config
        from apps.node.services.internal.local_platform_gateway import (
            LOCAL_PLATFORM_GATEWAY_METADATA,
        )

        gateway = MagicMock(
            id=7,
            name="platform-gateway",
            metadata=dict(LOCAL_PLATFORM_GATEWAY_METADATA),
        )
        link = MagicMock(
            gateway=gateway,
            config_json={},
            sl_lensnode_uuid=None,
        )
        link.resolved_workspace_root.return_value = "/workspace/platform"

        result = build_lens_enroll_config(link)

        self.assertEqual(
            result["lens_base_url"],
            "https://127.0.0.1:11443/sourcelens",
        )

    @patch(
        "apps.lens_bridge.deploy.local_platform_lens_gateway_base_url",
        return_value="https://127.0.0.1:11443/sourcelens",
    )
    @patch(
        "apps.lens_bridge.deploy.lens_gateway_base_url",
        return_value="https://console.example/sourcelens",
    )
    def test_unmanaged_gateway_keeps_public_lens_url(self, _public_url, _local_url):
        from apps.lens_bridge.services.provisioning import build_lens_enroll_config

        gateway = MagicMock(id=8, name="user-gateway", metadata={})
        link = MagicMock(
            gateway=gateway,
            config_json={},
            sl_lensnode_uuid=None,
        )
        link.resolved_workspace_root.return_value = "/workspace/user"

        result = build_lens_enroll_config(link)

        self.assertEqual(
            result["lens_base_url"],
            "https://console.example/sourcelens",
        )


class LensnodeDirPathsTests(SimpleTestCase):
    def test_collects_top_level_and_children(self):
        data = {
            "available_dirs": [
                {
                    "path": "/workspace/org-1/ks-1",
                    "children": [{"path": "/workspace/org-1/ks-1/data"}],
                }
            ]
        }
        paths = _lensnode_dir_paths(data)
        self.assertIn("/workspace/org-1/ks-1", paths)
        self.assertIn("/workspace/org-1/ks-1/data", paths)


class SlLensnodeSnapshotTests(SimpleTestCase):
    def test_extracts_display_fields(self):
        from apps.lens_bridge.services.provisioning import _extract_sl_lensnode_snapshot

        snap = _extract_sl_lensnode_snapshot(
            {
                "uuid": "de240f46-eccd-4e4b-868f-b1f504fbe67b",
                "name": "hfl-gw-134-zjb-134",
                "status": "online",
                "workspace_path": "/workspace/org-1",
                "agent_version": "0.1.0",
                "last_heartbeat_at": "2026-07-07T02:54:22.289738Z",
                "registered_at": "2026-07-06T09:16:24.641202Z",
                "tasks": [{"name": "knowledge_qa", "title": "Knowledge Q&A"}],
            }
        )
        self.assertEqual(snap["sl_name"], "hfl-gw-134-zjb-134")
        self.assertEqual(snap["sl_status"], "online")
        self.assertEqual(len(snap["sl_tasks"]), 1)
        self.assertEqual(snap["sl_tasks"][0]["title"], "Knowledge Q&A")


class EnsureKsWorkspaceTests(SimpleTestCase):
    @patch("apps.lens_bridge.services.provisioning.wait_for_lensnode_dir")
    @patch("apps.node.services.internal.agent_task.run_agent_task_sync")
    def test_dispatches_prepare_task(self, mock_sync, mock_wait):
        from apps.lens_bridge.services import provisioning

        task = MagicMock()
        task.last_error = ""
        mock_sync.return_value = MagicMock(ok=True, task=task)

        org = MagicMock()
        gateway = MagicMock(id=134)
        link = MagicMock()
        link.sl_lensnode_uuid = "de240f46-eccd-4e4b-868f-b1f504fbe67b"
        link.resolved_workspace_root.return_value = "/workspace/org-1"

        provisioning.ensure_ks_workspace_on_gateway(
            org=org,
            gateway=gateway,
            gateway_link=link,
            workspace_path="/workspace/org-1/ks-9",
        )

        mock_sync.assert_called_once()
        kwargs = mock_sync.call_args.kwargs
        self.assertEqual(kwargs["kind"], "lens.ks.prepare")
        self.assertEqual(kwargs["payload"]["path"], "/workspace/org-1/ks-9")
        mock_wait.assert_called_once()
