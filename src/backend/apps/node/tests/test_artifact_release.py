"""Tests for agent release artifact filename resolution."""

from __future__ import annotations


import pytest

from apps.node.api.views import artifact_release as release


@pytest.mark.parametrize(
    ("role", "platform", "arch", "ubuntu2404"),
    [
        ("agent", "linux", "amd64", False),
        ("proxy", "linux", "amd64", True),
        ("gateway", "linux", "arm64", True),
        ("proxy", "darwin", "amd64", False),
        ("gateway", "windows", "amd64", False),
    ],
)
def test_dist_filename_by_role(role, platform, arch, ubuntu2404):
    filename = release._dist_filename("1.0.0", platform, arch, ubuntu2404=ubuntu2404)
    if ubuntu2404:
        assert filename == f"hfl-agent-1.0.0-linux-{arch}-ubuntu2404.tar.gz"
    elif platform == "windows":
        assert filename == "hfl-agent-1.0.0-windows-amd64.zip"
    else:
        assert filename == f"hfl-agent-1.0.0-{platform}-{arch}.tar.gz"


def test_use_ubuntu2404_bundle_only_linux_proxy_gateway():
    assert release._use_ubuntu2404_bundle("proxy", "linux") is True
    assert release._use_ubuntu2404_bundle("gateway", "linux") is True
    assert release._use_ubuntu2404_bundle("agent", "linux") is False
    assert release._use_ubuntu2404_bundle("proxy", "darwin") is False


def test_get_agent_artifact_proxy_linux(tmp_path, monkeypatch):
    root = tmp_path / "agent-releases"
    version_dir = root / "1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "hfl-agent-1.0.0-linux-amd64-ubuntu2404.tar.gz").write_bytes(b"x")
    (version_dir / "hfl-agent-1.0.0-linux-amd64.tar.gz").write_bytes(b"y")

    monkeypatch.setattr(release, "_agent_releases_root", lambda: root)
    monkeypatch.delenv("AGENT_FILENAME", raising=False)
    monkeypatch.setenv("AGENT_VERSION", "1.0.0")

    artifact = release._get_agent_artifact("proxy", platform="linux", arch="amd64")
    assert artifact.filename == "hfl-agent-1.0.0-linux-amd64-ubuntu2404.tar.gz"
    assert artifact.artifact_path == (
        "/media/agent-releases/1.0.0/hfl-agent-1.0.0-linux-amd64-ubuntu2404.tar.gz"
    )


def test_get_agent_artifact_agent_linux(tmp_path, monkeypatch):
    root = tmp_path / "agent-releases"
    version_dir = root / "1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "hfl-agent-1.0.0-linux-amd64-ubuntu2404.tar.gz").write_bytes(b"x")
    (version_dir / "hfl-agent-1.0.0-linux-amd64.tar.gz").write_bytes(b"y")

    monkeypatch.setattr(release, "_agent_releases_root", lambda: root)
    monkeypatch.delenv("AGENT_FILENAME", raising=False)
    monkeypatch.setenv("AGENT_VERSION", "1.0.0")

    artifact = release._get_agent_artifact("agent", platform="linux", arch="amd64")
    assert artifact.filename == "hfl-agent-1.0.0-linux-amd64.tar.gz"


def test_try_acquire_slot_reuses_enrollment_id(monkeypatch):
    store: dict[str, set[str]] = {}

    class FakeRedis:
        def eval(self, script, numkeys, key, slot_id, maxn, ttl):  # noqa: ARG002
            members = store.setdefault(key, set())
            if slot_id in members:
                return [1, len(members)]
            members.add(slot_id)
            if len(members) > int(maxn):
                members.discard(slot_id)
                return [0, len(members)]
            return [1, len(members)]

    monkeypatch.setattr(release, "_redis_client", lambda: FakeRedis())
    monkeypatch.setenv("AGENT_RELEASES_TENANT_MAX_CONCURRENT_DOWNLOADS", "1")

    ok1, _ = release._try_acquire_slot("default", "enroll-token-a")
    ok2, _ = release._try_acquire_slot("default", "enroll-token-a")
    ok3, _ = release._try_acquire_slot("default", "enroll-token-b")

    assert ok1 is True
    assert ok2 is True
    assert ok3 is False

