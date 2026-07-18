"""Tests for published agent release version resolution."""

from __future__ import annotations


import pytest

from apps.node.services.internal.agent_release import (
    latest_published_agent_version,
    resolve_agent_version,
    semver_compare,
)


@pytest.fixture
def releases_root(tmp_path, settings, monkeypatch):
    media = tmp_path / "media" / "agent-releases"
    media.mkdir(parents=True)
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.delenv("AGENT_VERSION", raising=False)
    return media


def test_latest_published_agent_version_picks_highest_semver(releases_root):
    for version in ("1.0.0", "1.0.2", "1.0.10"):
        version_dir = releases_root / version
        version_dir.mkdir()
        (version_dir / f"hfl-agent-{version}-linux-amd64.tar.gz").write_bytes(b"x")
    assert latest_published_agent_version() == "1.0.10"


def test_latest_published_agent_version_honors_agent_version_env(releases_root, monkeypatch):
    for version in ("1.0.0", "1.0.2"):
        version_dir = releases_root / version
        version_dir.mkdir()
        (version_dir / f"hfl-agent-{version}-linux-amd64.tar.gz").write_bytes(b"x")
    monkeypatch.setenv("AGENT_VERSION", "1.0.0")
    assert latest_published_agent_version() == "1.0.0"


def test_resolve_agent_version_prefers_ubuntu2404_for_proxy(releases_root):
    version_dir = releases_root / "1.0.0"
    version_dir.mkdir()
    (version_dir / "hfl-agent-1.0.0-linux-amd64-ubuntu2404.tar.gz").write_bytes(b"x")
    assert resolve_agent_version("linux", "amd64", "proxy") == "1.0.0"


def test_semver_compare_orders_versions():
    assert semver_compare("1.0.0", "1.0.1") < 0
    assert semver_compare("1.0.1", "1.0.0") > 0
    assert semver_compare("1.0.0", "1.0.0") == 0
