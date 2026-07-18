from django.test import SimpleTestCase

from apps.lens_bridge.services.knowledge_source_sync import (
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
