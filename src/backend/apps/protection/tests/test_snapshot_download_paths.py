"""Tests for snapshot-download runtime paths."""

from __future__ import annotations

from apps.protection.services.snapshot_download import _artifact_root


def test_artifact_root_uses_configured_media_root(tmp_path, settings) -> None:
    """Generated downloads belong under the shared runtime media root."""
    settings.MEDIA_ROOT = tmp_path / "runtime-media"

    assert _artifact_root() == settings.MEDIA_ROOT / "snapshot-downloads"
