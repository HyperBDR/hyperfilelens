from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.lens_bridge.services import sl_client
from apps.lens_bridge.services.provisioning import _lensnode_matches_workspace


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


class LensnodeWorkspaceReadinessTests(SimpleTestCase):
    lensnode_uuid = "de240f46-eccd-4e4b-868f-b1f504fbe67b"

    def test_accepts_online_lensnode_at_workspace_root_without_deep_dirs(self):
        data = {
            "uuid": self.lensnode_uuid,
            "status": "online",
            "workspace_path": "/workspace/org-1/",
            "available_dirs": [],
        }
        self.assertTrue(
            _lensnode_matches_workspace(
                data,
                lensnode_uuid=self.lensnode_uuid,
                workspace_root="/workspace/org-1",
            )
        )

    def test_rejects_offline_or_wrong_workspace_lensnode(self):
        base = {
            "uuid": self.lensnode_uuid,
            "status": "offline",
            "workspace_path": "/workspace/org-1",
        }
        self.assertFalse(
            _lensnode_matches_workspace(
                base,
                lensnode_uuid=self.lensnode_uuid,
                workspace_root="/workspace/org-1",
            )
        )
        base["status"] = "online"
        base["workspace_path"] = "/workspace/another-root"
        self.assertFalse(
            _lensnode_matches_workspace(
                base,
                lensnode_uuid=self.lensnode_uuid,
                workspace_root="/workspace/org-1",
            )
        )


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
    @patch("apps.lens_bridge.services.gateway_execution.context_for_gateway_link")
    @patch("apps.lens_bridge.services.provisioning.wait_for_lensnode_ready")
    @patch("apps.node.services.internal.agent_task.run_agent_task_sync")
    def test_dispatches_prepare_task(self, mock_sync, mock_wait, mock_context):
        from apps.lens_bridge.services import provisioning

        task = MagicMock()
        task.last_error = ""
        mock_sync.return_value = MagicMock(ok=True, task=task)

        org = MagicMock(id=1)
        gateway = MagicMock(id=134)
        link = MagicMock(id=7)
        link.sl_lensnode_uuid = "de240f46-eccd-4e4b-868f-b1f504fbe67b"
        link.resolved_workspace_root.return_value = "/workspace/org-1"
        mock_context.return_value = MagicMock(
            gateway=gateway,
            execution_organization=MagicMock(id=99),
        )
        workspace_binding = MagicMock(
            gateway_link_id=7,
            execution_node_id=134,
            execution_organization_id=99,
            workspace_root="/workspace/org-1",
            workspace_uid="workspace-9",
            knowledge_source_id=9,
            workspace_kind="managed_restore",
        )
        workspace_binding.resolved_path.return_value = "/workspace/org-1/ks-9"

        provisioning.ensure_ks_workspace_on_gateway(
            org=org,
            gateway=gateway,
            gateway_link=link,
            workspace_binding=workspace_binding,
        )

        mock_sync.assert_called_once()
        kwargs = mock_sync.call_args.kwargs
        self.assertEqual(kwargs["kind"], "lens.ks.prepare")
        self.assertEqual(kwargs["payload"]["path"], "/workspace/org-1/ks-9")
        self.assertEqual(kwargs["payload"]["workspace_uid"], "workspace-9")
        self.assertEqual(kwargs["requesting_organization_id"], 1)
        mock_wait.assert_called_once()


class BrowseGatewayDirectoryTests(SimpleTestCase):
    @patch("apps.node.services.interface.run_agent_task_sync")
    @patch("apps.lens_bridge.services.provisioning.get_gateway_link")
    @patch("apps.lens_bridge.services.provisioning.require_gateway_node")
    def test_dispatches_restricted_gateway_browse(
        self,
        require_gateway,
        get_gateway_link,
        run_agent_task,
    ):
        from apps.lens_bridge.services.provisioning import browse_gateway_directory

        gateway = MagicMock(id=7, status="online")
        require_gateway.return_value = gateway
        link = MagicMock()
        link.resolved_workspace_root.return_value = "/workspace/org-1/data"
        get_gateway_link.return_value = link
        run_agent_task.return_value = MagicMock(
            ok=True,
            timed_out=False,
            result={
                "path": "/workspace/org-1/data/documents",
                "entries": [
                    {
                        "name": "reports",
                        "path": "/workspace/org-1/data/documents/reports",
                        "is_dir": True,
                    },
                    {
                        "name": "escape",
                        "path": "/etc",
                        "is_dir": True,
                    },
                ],
            },
        )

        result = browse_gateway_directory(
            org=MagicMock(id=1),
            gateway_id=7,
            path="/workspace/org-1/data/documents",
        )

        kwargs = run_agent_task.call_args.kwargs
        self.assertEqual(kwargs["kind"], "lens.gateway.browse")
        self.assertEqual(
            kwargs["payload"]["allowed_root"],
            "/workspace/org-1/data",
        )
        self.assertEqual(
            [entry["path"] for entry in result["entries"]],
            ["/workspace/org-1/data/documents/reports"],
        )

    @patch("apps.lens_bridge.services.provisioning.get_gateway_link")
    @patch("apps.lens_bridge.services.provisioning.require_gateway_node")
    def test_rejects_traversal_without_dispatching(
        self,
        require_gateway,
        get_gateway_link,
    ):
        from apps.lens_bridge.services.provisioning import browse_gateway_directory

        require_gateway.return_value = MagicMock(id=7, status="online")
        link = MagicMock()
        link.resolved_workspace_root.return_value = "/workspace/org-1/data"
        get_gateway_link.return_value = link

        with self.assertRaises(ValidationError):
            browse_gateway_directory(
                org=MagicMock(id=1),
                gateway_id=7,
                path="/workspace/org-1/data/../../etc",
            )
