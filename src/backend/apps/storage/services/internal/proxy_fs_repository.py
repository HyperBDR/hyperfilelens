"""Initialize or probe standalone-disk repositories on a Proxy node.

Mirrors :mod:`apps.storage.services.internal.nas_repository` but targets a
user-supplied directory on the Proxy node. The Agent-managed kopia engine
uses a strict create-only task for initialization and a separate connect-only
task for later probes.

See ``apps/agent/internal/engine/managed_backup.go`` for the agent-side
implementation of the ``repo.status`` task for ``proxy_fs`` repositories.
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.agent_log import log_agent_dispatch, log_agent_exception, log_agent_outcome
from apps.node.services.interface import run_agent_task_sync
from apps.storage.repositories.models import Repository
from apps.storage.services.internal.repository_errors import (
    REPOSITORY_ALREADY_EXISTS_MESSAGE,
    RepositoryAlreadyExistsError,
    agent_repository_failure_message,
    agent_result_has_repository_conflict,
)
from apps.storage.services.internal.repository_secrets import resolve_repository_secrets

logger = logging.getLogger(__name__)


class ProxyFSRepositoryError(RuntimeError):
    pass


def validate_proxy_for_proxy_fs(repository: Repository) -> Node:
    """Resolve the bound Proxy node; raise if the binding is invalid/offline."""
    if repository.repo_type != Repository.Type.PROXY_FS:
        raise ValidationError("Repository is not a proxy_fs repository.")
    if repository.bind_node_type != Repository.BindNodeType.PROXY or not repository.bind_node_id:
        raise ValidationError("Proxy filesystem repository is not bound to a proxy node.")
    node = Node.objects.filter(
        id=repository.bind_node_id,
        organization_id=repository.organization_id,
        role=NodeRole.PROXY,
        is_deleted=False,
    ).first()
    if node is None:
        raise ValidationError("Bound proxy node not found.")
    if node.status != Node.Status.ONLINE:
        raise ValidationError(f'Bound proxy node "{node.name}" is not online.')
    return node


def proxy_fs_repository_payload(repository: Repository) -> dict[str, Any]:
    """Build the agent-side ``repository`` payload for a proxy_fs repository."""
    config = repository.config if isinstance(repository.config, dict) else {}
    secrets_payload = resolve_repository_secrets(repository)
    return {
        "id": repository.id,
        "type": Repository.Type.PROXY_FS,
        "path": str(config.get("proxy_node_dir") or "").strip(),
        "kopia_password": str(secrets_payload.get("kopia_password") or "").strip(),
    }


def initialize_proxy_fs_repository(repository: Repository):
    """Initialize a new proxy_fs repository on the bound Proxy node."""

    return _run_proxy_fs_repository_task(
        repository,
        kind="repo.initialize",
        log_scope="storage proxy_fs repo init",
    )


def check_proxy_fs_repository(repository: Repository):
    return _run_proxy_fs_repository_task(
        repository,
        kind="repo.status",
        log_scope="storage proxy_fs repo check",
    )


def _run_proxy_fs_repository_task(
    repository: Repository,
    *,
    kind: str,
    log_scope: str,
):
    """Run a strict initialize or connect-only probe on the bound Proxy."""

    node = validate_proxy_for_proxy_fs(repository)
    payload = {
        "repository": proxy_fs_repository_payload(repository),
    }
    log_agent_dispatch(
        log_scope,
        node_id=node.id,
        kind=kind,
        correlation_type="storage_repository",
        correlation_id=str(repository.id),
        repository_id=repository.id,
        org_id=repository.organization_id,
    )
    try:
        outcome = run_agent_task_sync(
            organization_id=repository.organization_id,
            node_id=node.id,
            kind=kind,
            payload=payload,
            correlation_type="storage_repository",
            correlation_id=str(repository.id),
            wait_timeout_seconds=180,
        )
    except Exception as exc:
        log_agent_exception(
            log_scope,
            node_id=node.id,
            kind=kind,
            exc=exc,
            correlation_type="storage_repository",
            correlation_id=str(repository.id),
            repository_id=repository.id,
        )
        raise ProxyFSRepositoryError(str(exc)) from exc
    log_agent_outcome(
        log_scope,
        outcome=outcome,
        node_id=node.id,
        kind=kind,
        correlation_type="storage_repository",
        correlation_id=str(repository.id),
        repository_id=repository.id,
    )
    if outcome.task.status != "success":
        if agent_result_has_repository_conflict(outcome.result):
            raise RepositoryAlreadyExistsError(REPOSITORY_ALREADY_EXISTS_MESSAGE)
        message = agent_repository_failure_message(
            outcome.result,
            last_error=str(getattr(outcome.task, "last_error", "") or ""),
        )
        raise ProxyFSRepositoryError(message or "Proxy filesystem repository initialization failed.")
    logger.info(
        "%s ok repository_id=%s node_id=%s org_id=%s",
        log_scope,
        repository.id,
        node.id,
        repository.organization_id,
    )
    return outcome
