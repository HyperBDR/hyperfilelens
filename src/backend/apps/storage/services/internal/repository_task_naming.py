from __future__ import annotations

from apps.node.models import Node, NodeRole
from apps.storage.repositories.models import Repository, RepositoryExecutionTarget


def repository_operation_display_name(
    *,
    action_label: str,
    repository: Repository,
    target: RepositoryExecutionTarget | None,
) -> str:
    """Return a user-facing repository operation name for the execution scope."""
    source_name = _direct_nas_source_name(repository=repository, target=target)
    object_name = source_name or repository.name
    return f"{action_label} · {object_name}"


def _direct_nas_source_name(
    *,
    repository: Repository,
    target: RepositoryExecutionTarget | None,
) -> str:
    if (
        target is None
        or repository.repo_type != Repository.Type.NAS
        or repository.bind_node_id is not None
        or not target.repository_subdir
    ):
        return ""

    node_id = target.owner_node_id
    if node_id is None:
        return str(target.repository_subdir or target.target_key).strip()

    source_name = str(
        Node.all_objects.filter(
            organization_id=repository.organization_id,
            id=node_id,
            role=NodeRole.AGENT,
        ).values_list("name", flat=True).first()
        or ""
    ).strip()
    if not source_name:
        return f"Backup Source #{node_id}"

    sibling_node_ids = list(
        RepositoryExecutionTarget.objects.filter(
            repository=repository,
            organization_id=repository.organization_id,
            is_active=True,
            owner_node_id__isnull=False,
        )
        .exclude(pk=target.pk)
        .values_list("owner_node_id", flat=True)
    )
    has_duplicate = Node.all_objects.filter(
        organization_id=repository.organization_id,
        id__in=sibling_node_ids,
        role=NodeRole.AGENT,
        name=source_name,
    ).exists()
    return f"{source_name} (#{node_id})" if has_duplicate else source_name


__all__ = ["repository_operation_display_name"]
