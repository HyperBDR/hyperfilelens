from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.storage.repositories.models import Repository
from apps.storage.services.internal.repository_secrets import build_repository_runtime_payload


EXPLICIT_REPOSITORY_SERVER_HOST_KEYS = (
    "proxy_repository_server_host",
    "repository_server_host",
    "advertised_host",
    "advertise_host",
)

_DNS_HOST_RE = re.compile(
    r"^(?=.{1,253}\.?$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.?$"
)


def normalize_repository_server_host(value: object) -> str:
    host = str(value or "").strip()
    if not host:
        return ""
    if "://" in host or "/" in host or any(char.isspace() for char in host):
        raise ValueError("Enter an IPv4, IPv6, or DNS host without a scheme, path, or port.")
    unbracketed = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        return ipaddress.ip_address(unbracketed).compressed
    except ValueError:
        pass
    if ":" in host or not _DNS_HOST_RE.fullmatch(host):
        raise ValueError("Enter a valid IPv4, IPv6, or DNS host without a port.")
    return host.rstrip(".").lower()


@dataclass(frozen=True)
class RepositoryExecutionTarget:
    node: Node
    source_type: str = "agent"
    source_ref_id: int = 0


@dataclass(frozen=True)
class RepositoryAccess:
    node: Node
    repository_payload: dict[str, Any]
    mode: str


def resolve_repository_reader(
    *,
    repository: Repository,
    fallback_node: Node | None,
    source_type: str = "agent",
    source_ref_id: int | None = None,
) -> RepositoryAccess:
    """Resolve the node that is allowed to read/write the repository.

    Proxy-bound NAS and proxy_fs repositories are central storage endpoints:
    their bound Proxy is the only node that may receive the full repository
    payload. Other repository types keep the existing local execution model.
    """

    if repository.repo_type == Repository.Type.NAS and repository.bind_node_type == Repository.BindNodeType.PROXY:
        node = _bound_proxy(repository=repository, message_prefix="NAS repository")
        return _access(repository=repository, node=node, source_type="proxy", source_ref_id=node.id, mode="bound_proxy")

    if repository.repo_type == Repository.Type.PROXY_FS:
        node = _bound_proxy(repository=repository, message_prefix="Proxy filesystem repository")
        return _access(repository=repository, node=node, source_type="proxy", source_ref_id=node.id, mode="bound_proxy")

    if fallback_node is None:
        raise ValidationError({"repository_id": "Repository access requires an execution node."})
    return _access(
        repository=repository,
        node=fallback_node,
        source_type=source_type,
        source_ref_id=source_ref_id if source_ref_id is not None else int(fallback_node.id),
        mode="fallback_node",
    )


def repository_payload_for_node(
    *,
    repository: Repository,
    node: Node,
    source_type: str = "agent",
    source_ref_id: int | None = None,
) -> dict[str, Any]:
    """Build a repository payload for a specific execution node.

    This is intentionally strict for Proxy-bound repositories. Callers that
    want the correct reader should use :func:`resolve_repository_reader`.
    """

    target = RepositoryExecutionTarget(
        node=node,
        source_type=source_type,
        source_ref_id=source_ref_id if source_ref_id is not None else int(node.id),
    )
    return build_repository_runtime_payload(repository=repository, execution_target=target)


def repository_uses_bound_proxy(repository: Repository) -> bool:
    return (
        repository.repo_type == Repository.Type.PROXY_FS
        or (
            repository.repo_type == Repository.Type.NAS
            and repository.bind_node_type == Repository.BindNodeType.PROXY
        )
    )


def explicit_repository_server_host(*, repository: Repository, node: Node) -> tuple[str, str]:
    """Return an explicitly advertised cross-node repository server host.

    Generic inventory addresses and node names are intentionally excluded:
    they frequently contain control-plane, NAT, or container bridge addresses
    that are not reachable from another backup node.
    """

    config = repository.config if isinstance(repository.config, dict) else {}
    for key in EXPLICIT_REPOSITORY_SERVER_HOST_KEYS:
        try:
            value = normalize_repository_server_host(config.get(key))
        except ValueError:
            return "", f"repository.config.{key}"
        if value:
            return value, f"repository.config.{key}"

    metadata = node.metadata if isinstance(node.metadata, dict) else {}
    inventory = metadata.get("inventory") if isinstance(metadata.get("inventory"), dict) else {}
    for source_name, source in (("metadata", metadata), ("metadata.inventory", inventory)):
        for key in EXPLICIT_REPOSITORY_SERVER_HOST_KEYS:
            try:
                value = normalize_repository_server_host(source.get(key))
            except ValueError:
                return "", f"node.{source_name}.{key}"
            if value:
                return value, f"node.{source_name}.{key}"
    return "", ""


def _access(
    *,
    repository: Repository,
    node: Node,
    source_type: str,
    source_ref_id: int,
    mode: str,
) -> RepositoryAccess:
    return RepositoryAccess(
        node=node,
        repository_payload=repository_payload_for_node(
            repository=repository,
            node=node,
            source_type=source_type,
            source_ref_id=source_ref_id,
        ),
        mode=mode,
    )


def _bound_proxy(*, repository: Repository, message_prefix: str) -> Node:
    if repository.bind_node_type != Repository.BindNodeType.PROXY or not repository.bind_node_id:
        raise ValidationError({"repository_id": f"{message_prefix} is not bound to a proxy node."})
    node = Node.objects.filter(
        id=repository.bind_node_id,
        organization_id=repository.organization_id,
        role=NodeRole.PROXY,
        is_deleted=False,
    ).first()
    if node is None:
        raise ValidationError({"repository_id": f"{message_prefix} bound proxy node not found."})
    if node.status != Node.Status.ONLINE:
        raise ValidationError({"repository_id": f'{message_prefix} bound proxy node "{node.name}" is offline.'})
    return node


__all__ = [
    "RepositoryAccess",
    "RepositoryExecutionTarget",
    "normalize_repository_server_host",
    "repository_payload_for_node",
    "repository_uses_bound_proxy",
    "explicit_repository_server_host",
    "resolve_repository_reader",
]
