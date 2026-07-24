"""Tests for agent release artifact filename resolution."""

from __future__ import annotations


import pytest

from apps.node.api.views import artifact_release as release
from apps.node.services.internal import agent_release as release_service


@pytest.mark.parametrize(
    ("role", "platform", "arch", "ubuntu_release"),
    [
        ("agent", "linux", "amd64", None),
        ("proxy", "linux", "amd64", "20.04"),
        ("gateway", "linux", "arm64", "24.04"),
        ("proxy", "darwin", "amd64", None),
        ("gateway", "windows", "amd64", None),
    ],
)
def test_dist_filename_by_role(role, platform, arch, ubuntu_release):
    filename = release._dist_filename(
        "1.0.0",
        platform,
        arch,
        ubuntu_release=ubuntu_release,
    )
    if ubuntu_release:
        suffix = "ubuntu" + ubuntu_release.replace(".", "")
        assert filename == f"hfl-agent-1.0.0-linux-{arch}-{suffix}.tar.gz"
    elif platform == "windows":
        assert filename == "hfl-agent-1.0.0-windows-amd64.zip"
    else:
        assert filename == f"hfl-agent-1.0.0-{platform}-{arch}.tar.gz"


def test_ubuntu_bundle_release_uses_reported_host_version():
    assert release._ubuntu_bundle_release("proxy", "linux", "20.04") == "20.04"
    assert release._ubuntu_bundle_release("gateway", "linux", "24.04.2") == "24.04"
    assert release._ubuntu_bundle_release("agent", "linux", "20.04") is None
    assert release._ubuntu_bundle_release("proxy", "darwin", "24.04") is None
    assert release._ubuntu_bundle_release("gateway", "linux", "22.04") == "22.04"


def test_ubuntu_bundle_release_preserves_legacy_2404_default():
    assert release._ubuntu_bundle_release("gateway", "linux") == "24.04"


@pytest.mark.parametrize(
    ("os_version", "suffix"),
    [
        ("20.04", "ubuntu2004"),
        ("22.04", "ubuntu2204"),
        ("24.04", "ubuntu2404"),
    ],
)
def test_get_agent_artifact_proxy_linux(tmp_path, monkeypatch, os_version, suffix):
    root = tmp_path / "agent-releases"
    version_dir = root / "1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "hfl-agent-1.0.0-linux-amd64-ubuntu2404.tar.gz").write_bytes(b"x")
    (version_dir / "hfl-agent-1.0.0-linux-amd64-ubuntu2204.tar.gz").write_bytes(b"w")
    (version_dir / "hfl-agent-1.0.0-linux-amd64-ubuntu2004.tar.gz").write_bytes(b"z")
    (version_dir / "hfl-agent-1.0.0-linux-amd64.tar.gz").write_bytes(b"y")

    monkeypatch.setattr(release_service, "agent_releases_root", lambda: root)
    monkeypatch.delenv("AGENT_FILENAME", raising=False)
    monkeypatch.setenv("AGENT_VERSION", "1.0.0")

    artifact = release._get_agent_artifact(
        "proxy",
        platform="linux",
        arch="amd64",
        os_version=os_version,
    )
    assert artifact.filename == f"hfl-agent-1.0.0-linux-amd64-{suffix}.tar.gz"
    assert artifact.artifact_path == (
        f"/media/agent-releases/1.0.0/hfl-agent-1.0.0-linux-amd64-{suffix}.tar.gz"
    )


def test_get_agent_artifact_agent_linux(tmp_path, monkeypatch):
    root = tmp_path / "agent-releases"
    version_dir = root / "1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "hfl-agent-1.0.0-linux-amd64-ubuntu2404.tar.gz").write_bytes(b"x")
    (version_dir / "hfl-agent-1.0.0-linux-amd64.tar.gz").write_bytes(b"y")

    monkeypatch.setattr(release_service, "agent_releases_root", lambda: root)
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
