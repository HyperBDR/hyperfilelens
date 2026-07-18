"""Tests for agent.upgrade dispatch validation."""

from __future__ import annotations


import pytest

from apps.node.exceptions import AgentUpgradeError
from apps.node.models import Node
from apps.node.services.internal.agent_upgrade import node_platform_arch, validate_agent_upgrade


@pytest.fixture
def releases_root(tmp_path, settings, monkeypatch):
    media = tmp_path / "media" / "agent-releases"
    media.mkdir(parents=True)
    version_dir = media / "1.0.1"
    version_dir.mkdir()
    (version_dir / "hfl-agent-1.0.1-linux-amd64.tar.gz").write_bytes(b"x")
    (version_dir / "hfl-agent-1.0.1-linux-amd64-ubuntu2404.tar.gz").write_bytes(b"x")
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.delenv("AGENT_VERSION", raising=False)
    return media


def test_validate_agent_upgrade_rejects_offline(releases_root):
    node = Node(role=Node.Role.AGENT, status=Node.Status.OFFLINE, version="1.0.0")
    with pytest.raises(AgentUpgradeError, match="offline") as exc:
        validate_agent_upgrade(node=node)
    assert exc.value.code == "node_offline"


def test_validate_agent_upgrade_accepts_same_version(releases_root):
    node = Node(
        role=Node.Role.AGENT,
        status=Node.Status.ONLINE,
        version="1.0.1",
        metadata={"inventory": {"os": "linux", "arch": "amd64"}},
    )
    assert validate_agent_upgrade(node=node) == "1.0.1"


def test_validate_agent_upgrade_rejects_downgrade(releases_root):
    node = Node(
        role=Node.Role.AGENT,
        status=Node.Status.ONLINE,
        version="9.9.9",
        metadata={"inventory": {"os": "linux", "arch": "amd64"}},
    )
    with pytest.raises(AgentUpgradeError, match="downgrade") as exc:
        validate_agent_upgrade(node=node)
    assert exc.value.code == "downgrade_not_supported"


def test_validate_agent_upgrade_accepts_lower_current(releases_root):
    node = Node(
        role=Node.Role.PROXY,
        status=Node.Status.ONLINE,
        version="1.0.0",
        metadata={"inventory": {"os": "linux", "arch": "amd64"}},
    )
    assert validate_agent_upgrade(node=node) == "1.0.1"


def test_node_platform_arch_treats_darwin_as_macos_not_windows():
    node = Node(
        role=Node.Role.AGENT,
        status=Node.Status.ONLINE,
        os_name="darwin arm64",
        metadata={"inventory": {"os": "darwin", "arch": "arm64"}},
    )
    assert node_platform_arch(node) == ("darwin", "arm64")
