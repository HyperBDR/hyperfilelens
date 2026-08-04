"""Minimal installer metadata materialization checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.node.api.views.installer_metadata import _manifest_is_materialized


class InstallerMetadataTests(SimpleTestCase):
    def test_accepts_complete_versioned_installer_matrix(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = self._write_matrix(root)

            self.assertTrue(_manifest_is_materialized(root, payload))

    def test_rejects_path_traversal(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = self._write_matrix(root)
            payload["artifacts"]["linux-amd64"]["filename"] = "../outside"

            self.assertFalse(_manifest_is_materialized(root, payload))

    @staticmethod
    def _write_matrix(root: Path) -> dict:
        artifacts = {}
        for key, extension in {
            "linux-amd64": "tar.gz",
            "linux-arm64": "tar.gz",
            "darwin-amd64": "tar.gz",
            "darwin-arm64": "tar.gz",
            "windows-amd64": "zip",
        }.items():
            filename = f"1.0.0/hfl-installer-{key}.{extension}"
            path = root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            content = key.encode("ascii")
            path.write_bytes(content)
            artifacts[key] = {
                "filename": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        return {"schema_version": 1, "artifacts": artifacts}
