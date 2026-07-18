"""Proxy force-decommission: cleanup-only for NAS bindings, then remove the Proxy node."""

from __future__ import annotations

import logging
from typing import Any

from apps.iam.models import Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.bindings import collect_proxy_bindings
from apps.protection.models import BackupConfig
from apps.source.constants import MountStatus, ResourceStatus
from apps.source.models import SourceResource
from apps.source.services.interface import unmount_resource
from apps.storage.repositories.models import Repository

logger = logging.getLogger(__name__)


class ProxyDecommissionBlocked(Exception):
    def __init__(self, *, message: str, code: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or []


def preflight_force_proxy_decommission(
    *,
    organization_id: int,
    proxy_id: int,
) -> dict[str, Any]:
    bindings = collect_proxy_bindings(organization_id=organization_id, proxy_id=proxy_id)
    blocking: list[dict[str, Any]] = []

    for row in bindings.standalone_disk_repositories:
        repo_id = int(row["id"])
        repo_name = str(row.get("name") or repo_id)
        if BackupConfig.objects.filter(
            organization_id=organization_id,
            repository_id=repo_id,
        ).exists():
            blocking.append(
                {
                    "code": "proxy_fs_in_use",
                    "detail": (
                        f"Local disk repository \"{repo_name}\" is used by backup sources. "
                        "Unregister those backup sources before deleting the Proxy."
                    ),
                    "repository_id": repo_id,
                    "repository_name": repo_name,
                }
            )
            continue
        blocking.append(
            {
                "code": "proxy_fs_bound",
                "detail": (
                    f"Local disk repository \"{repo_name}\" is bound to this Proxy. "
                    "Remove the repository before deleting the Proxy."
                ),
                "repository_id": repo_id,
                "repository_name": repo_name,
            }
        )

    return {
        "blocking": blocking,
        "decommission_disabled": bool(blocking),
        "bindings": bindings.to_payload(),
    }


def force_cleanup_proxy_bindings(
    *,
    org: Organization,
    proxy: Node,
    user=None,
) -> dict[str, Any]:
    """Cleanup-only for Source NAS and Target NAS repos; retain inventory for rebind."""
    if proxy.role != NodeRole.PROXY:
        raise ValueError("force_cleanup_proxy_bindings applies to Proxy nodes only")

    bindings = collect_proxy_bindings(organization_id=org.id, proxy_id=proxy.id)
    preflight = preflight_force_proxy_decommission(organization_id=org.id, proxy_id=proxy.id)
    if preflight["decommission_disabled"]:
        raise ProxyDecommissionBlocked(
            message="Proxy cannot be force-deleted while local disk repositories remain bound.",
            code="proxy_fs_blocked",
            details=preflight["blocking"],
        )

    if proxy.status != Node.Status.ONLINE:
        raise ProxyDecommissionBlocked(
            message="Proxy must be online to force-delete with NAS cleanup.",
            code="proxy_offline",
        )

    warnings: list[dict[str, Any]] = []
    cleaned_source_nas: list[int] = []
    cleaned_target_repos: list[int] = []

    for row in bindings.source_nas_resources:
        resource = SourceResource.objects.filter(
            pk=int(row["id"]),
            organization_id=org.id,
            is_deleted=False,
        ).first()
        if resource is None:
            continue
        if resource.mount_status == MountStatus.MOUNTED:
            result = unmount_resource(resource=resource)
            if not result.get("success"):
                warnings.append(
                    {
                        "code": "nas_umount_failed",
                        "detail": str(result.get("message") or "NAS unmount failed."),
                        "source_resource_id": resource.id,
                        "source_name": resource.name,
                    }
                )
        resource.bound_node = None
        resource.mount_status = MountStatus.UNMOUNTED
        resource.mount_point = ""
        resource.status = ResourceStatus.INACTIVE
        resource.status_message = "needs_proxy"
        resource.save(
            update_fields=[
                "bound_node",
                "mount_status",
                "mount_point",
                "status",
                "status_message",
                "updated_at",
            ]
        )
        cleaned_source_nas.append(resource.id)

    for row in bindings.target_nas_repositories:
        repo = Repository.objects.filter(
            pk=int(row["id"]),
            organization_id=org.id,
        ).exclude(status=Repository.Status.REMOVED).first()
        if repo is None:
            continue
        config = dict(repo.config or {})
        config["needs_proxy"] = True
        config["former_bind_node_id"] = proxy.id
        repo.bind_node_id = None
        repo.health = Repository.Health.OFFLINE
        repo.config = config
        repo.save(update_fields=["bind_node_id", "health", "config", "updated_at"])
        cleaned_target_repos.append(repo.id)

    logger.info(
        "proxy force cleanup org_id=%s proxy_id=%s source_nas=%s target_repos=%s warnings=%s",
        org.id,
        proxy.id,
        cleaned_source_nas,
        cleaned_target_repos,
        len(warnings),
    )
    return {
        "cleaned_source_nas_ids": cleaned_source_nas,
        "cleaned_target_nas_repository_ids": cleaned_target_repos,
        "warnings": warnings,
    }


__all__ = [
    "ProxyDecommissionBlocked",
    "force_cleanup_proxy_bindings",
    "preflight_force_proxy_decommission",
]
