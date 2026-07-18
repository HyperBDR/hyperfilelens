from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.storage.repositories.models import Repository
from apps.storage.services.internal.repository_secrets import build_repository_runtime_payload


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
    "repository_payload_for_node",
    "repository_uses_bound_proxy",
    "resolve_repository_reader",
]
