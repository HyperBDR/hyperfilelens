from __future__ import annotations

import logging

from django.apps import apps
from django.core.exceptions import ValidationError

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.agent_log import (
    log_agent_dispatch,
    log_agent_exception,
    log_agent_outcome,
)
from apps.node.services.interface import run_agent_task_sync
from apps.source.constants import ResourceType
from apps.storage.repositories.models import Repository
from apps.storage.services.internal.nas_repository import (
    check_proxy_nas_repository,
    nas_agent_repository_subdir,
    nas_repository_payload,
)
from apps.storage.services.internal.proxy_fs_repository import (
    check_proxy_fs_repository,
)
from apps.storage.services.internal.repository_initializer import check_s3_repository


logger = logging.getLogger(__name__)


def probe_repository_health(repository: Repository) -> str:
    """Probe a repository without persisting health, timestamps, or usage."""
    if repository.repo_type == Repository.Type.S3:
        check_s3_repository(repository)
        return Repository.Health.ONLINE

    if repository.repo_type == Repository.Type.PROXY_FS:
        check_proxy_fs_repository(repository, health_only=True)
        return Repository.Health.ONLINE

    if repository.repo_type == Repository.Type.NAS:
        if (
            repository.bind_node_type == Repository.BindNodeType.PROXY
            and repository.bind_node_id
        ):
            check_proxy_nas_repository(repository, health_only=True)
            return Repository.Health.ONLINE
        if not repository.bind_node_type and not repository.bind_node_id:
            return probe_unbound_nas_repository_health(repository)
        raise ValidationError("NAS repository proxy binding is incomplete.")

    raise ValidationError(f"Repository type {repository.repo_type} is not supported.")


def probe_unbound_nas_repository_health(repository: Repository) -> str:
    """Return Online when any associated execution node can access the NAS."""
    if (
        repository.repo_type != Repository.Type.NAS
        or repository.bind_node_type
        or repository.bind_node_id
    ):
        raise ValidationError("Repository is not an unbound NAS repository.")

    has_associations, nodes = _unbound_nas_execution_nodes(repository)
    if not has_associations:
        return Repository.Health.UNVERIFIED

    for node in nodes:
        if node.status != Node.Status.ONLINE:
            continue
        if _probe_unbound_nas_from_node(repository=repository, node=node):
            return Repository.Health.ONLINE
    return Repository.Health.OFFLINE


def _unbound_nas_execution_nodes(repository: Repository) -> tuple[bool, list[Node]]:
    backup_config_model = apps.get_model("protection", "BackupConfig")
    rows = list(
        backup_config_model.objects.filter(
            organization_id=repository.organization_id,
            repository_id=repository.id,
        )
        .order_by("id")
        .values_list("source_type", "source_ref_id")
    )
    if not rows:
        return False, []

    agent_ids = {
        int(source_ref_id)
        for source_type, source_ref_id in rows
        if source_type == "agent" and int(source_ref_id or 0) > 0
    }
    nas_source_ids = {
        int(source_ref_id)
        for source_type, source_ref_id in rows
        if source_type == "nas" and int(source_ref_id or 0) > 0
    }

    nodes: dict[int, Node] = {
        int(node.id): node
        for node in Node.objects.filter(
            organization_id=repository.organization_id,
            id__in=agent_ids,
            role=NodeRole.AGENT,
            is_deleted=False,
        )
    }
    if nas_source_ids:
        source_resource_model = apps.get_model("source", "SourceResource")
        proxy_ids = set(
            source_resource_model.objects.filter(
                organization_id=repository.organization_id,
                id__in=nas_source_ids,
                resource_type=ResourceType.NAS,
                is_deleted=False,
                bound_node_id__isnull=False,
            ).values_list("bound_node_id", flat=True)
        )
        nodes.update(
            {
                int(node.id): node
                for node in Node.objects.filter(
                    organization_id=repository.organization_id,
                    id__in=proxy_ids,
                    role=NodeRole.PROXY,
                    is_deleted=False,
                )
            }
        )
    return True, [nodes[node_id] for node_id in sorted(nodes)]


def _probe_unbound_nas_from_node(*, repository: Repository, node: Node) -> bool:
    log_scope = "storage direct nas health probe"
    payload = {
        "repository": nas_repository_payload(
            repository=repository,
            subdir=nas_agent_repository_subdir(node.id),
            node_id=node.id,
        ),
        "health_only": True,
    }
    log_agent_dispatch(
        log_scope,
        node_id=node.id,
        kind="repo.status",
        correlation_type="storage_repository",
        correlation_id=str(repository.id),
        repository_id=repository.id,
        org_id=repository.organization_id,
    )
    try:
        outcome = run_agent_task_sync(
            organization_id=repository.organization_id,
            node_id=node.id,
            kind="repo.status",
            payload=payload,
            correlation_type="storage_repository",
            correlation_id=str(repository.id),
            wait_timeout_seconds=180,
        )
    except Exception as exc:
        log_agent_exception(
            log_scope,
            node_id=node.id,
            kind="repo.status",
            exc=exc,
            correlation_type="storage_repository",
            correlation_id=str(repository.id),
            repository_id=repository.id,
        )
        logger.warning(
            "direct NAS health path failed repository_id=%s node_id=%s error_type=%s",
            repository.id,
            node.id,
            type(exc).__name__,
        )
        return False

    log_agent_outcome(
        log_scope,
        outcome=outcome,
        node_id=node.id,
        kind="repo.status",
        correlation_type="storage_repository",
        correlation_id=str(repository.id),
        repository_id=repository.id,
    )
    return outcome.task.status == "success"
