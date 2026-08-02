from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.lens_bridge.services.knowledge_source_sync import (
    _run_phase_push_assistant,
    _restore_selected_paths,
    map_scope_to_workspace,
)


class MapScopeToWorkspaceTests(SimpleTestCase):
    def test_maps_relative_paths_under_common_prefix(self):
        workspace = "/workspace/org-1/ks-42"
        scopes = ["/data/docs", "/data/images"]
        self.assertEqual(
            map_scope_to_workspace(
                workspace_root=workspace,
                scope_paths=scopes,
                scope_path="/data/docs",
            ),
            "/workspace/org-1/ks-42/docs",
        )
        self.assertEqual(
            map_scope_to_workspace(
                workspace_root=workspace,
                scope_paths=scopes,
                scope_path="/data/images",
            ),
            "/workspace/org-1/ks-42/images",
        )

    def test_single_scope_uses_basename_when_equal_to_common(self):
        workspace = "/workspace/org-1/ks-7"
        self.assertEqual(
            map_scope_to_workspace(
                workspace_root=workspace,
                scope_paths=["/backup/root"],
                scope_path="/backup/root",
            ),
            "/workspace/org-1/ks-7/root",
        )

    def test_windows_scope_maps_relative_subpath(self):
        workspace = "/workspace/org-1/ks-7"
        scope = r"D:\AndroidStudioProjects\VidLingo\app\src\main"
        self.assertEqual(
            map_scope_to_workspace(
                workspace_root=workspace,
                scope_paths=[scope],
                scope_path=scope,
            ),
            "/workspace/org-1/ks-7/main",
        )

    def test_restore_selected_paths_relative_to_directory(self):
        self.assertEqual(
            _restore_selected_paths(
                directory_source_path=r"D:\AndroidStudioProjects",
                scope_path=r"D:\AndroidStudioProjects\VidLingo\app\src\main",
            ),
            ["VidLingo/app/src/main"],
        )
        self.assertEqual(
            _restore_selected_paths(
                directory_source_path="/data",
                scope_path="/data/docs",
            ),
            ["docs"],
        )
        self.assertEqual(
            _restore_selected_paths(
                directory_source_path="/data",
                scope_path="/data",
            ),
            [],
        )


class PushAssistantPhaseTests(SimpleTestCase):
    @patch(
        "apps.lens_bridge.services.knowledge_source_sync."
        "provisioning.sync_linked_assistant_for_ks"
    )
    @patch(
        "apps.lens_bridge.services.knowledge_source_sync."
        "provisioning.wait_for_lensnode_ready"
    )
    @patch(
        "apps.lens_bridge.services.knowledge_source_sync."
        "context_for_knowledge_source"
    )
    @patch("apps.lens_bridge.services.knowledge_source_sync._update_sync_phase")
    def test_waits_for_authoritative_gateway_workspace_root(
        self,
        _update_phase,
        context_for_source,
        wait_for_ready,
        sync_assistant,
    ):
        organization = MagicMock()
        knowledge_source = MagicMock(
            backup_source_snapshot_id=1,
            backup_snapshot_directory_id=1,
            workspace_path_on_lensnode="/workspace/org-34/data/hfl-ks-ready",
        )
        gateway_link = MagicMock()
        gateway_link.sl_lensnode_uuid = "de240f46-eccd-4e4b-868f-b1f504fbe67b"
        gateway_link.resolved_workspace_root.return_value = "/workspace/org-34/data"
        context_for_source.return_value = MagicMock(gateway_link=gateway_link)

        _run_phase_push_assistant(
            org=organization,
            ks=knowledge_source,
            sync_state={},
        )

        wait_for_ready.assert_called_once_with(
            lensnode_uuid=gateway_link.sl_lensnode_uuid,
            workspace_root="/workspace/org-34/data",
            selected_dir="/workspace/org-34/data/hfl-ks-ready",
        )
        sync_assistant.assert_called_once_with(
            org=organization,
            ks=knowledge_source,
            gateway_link=gateway_link,
        )
