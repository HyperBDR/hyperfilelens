"""Collect license usage statistics for an organization."""

from __future__ import annotations

from apps.iam.models import Membership, Organization
from apps.subscription.constants import UNLIMITED


def collect_usage_stats(*, organization_id: int) -> dict:
    org = Organization.objects.filter(id=organization_id).first()
    if org is None:
        return _empty_usage()

    users_count = Membership.objects.filter(organization_id=organization_id, is_active=True).count()
    nodes_count = 0
    agents_count = 0
    proxies_count = 0
    gateways_count = 0
    source_nas_count = 0
    object_storage_count = 0
    target_nas_count = 0
    standalone_disk_count = 0
    alert_policies_count = 0
    try:
        from apps.node.models import Node
        from apps.node.models.base import NodeRole

        node_qs = Node.objects.filter(organization_id=organization_id)
        nodes_count = node_qs.count()
        agents_count = node_qs.filter(role=NodeRole.AGENT).count()
        proxies_count = node_qs.filter(role=NodeRole.PROXY).count()
        gateways_count = node_qs.filter(role=NodeRole.GATEWAY).count()
    except Exception:
        pass
    try:
        from apps.source.constants import ResourceType
        from apps.source.models import SourceResource

        source_nas_count = SourceResource.objects.filter(
            organization_id=organization_id,
            resource_type__in=(ResourceType.NAS, ResourceType.NFS, ResourceType.CIFS),
        ).count()
    except Exception:
        pass
    try:
        from apps.storage.repositories.models import Repository

        repo_qs = Repository.objects.filter(organization_id=organization_id)
        object_storage_count = repo_qs.filter(repo_type=Repository.Type.S3).count()
        target_nas_count = repo_qs.filter(repo_type=Repository.Type.NAS).count()
        standalone_disk_count = repo_qs.filter(repo_type=Repository.Type.PROXY_FS).count()
    except Exception:
        pass
    try:
        from apps.alert.models import AlertPolicy

        alert_policies_count = AlertPolicy.objects.filter(organization_id=organization_id).count()
    except Exception:
        pass

    return {
        "organizations_count": Organization.objects.filter(is_active=True).count(),
        "users_count": users_count,
        "nodes_count": nodes_count,
        "agents_count": agents_count,
        "proxies_count": proxies_count,
        "gateways_count": gateways_count,
        "source_nas_count": source_nas_count,
        "object_storage_count": object_storage_count,
        "target_nas_count": target_nas_count,
        "standalone_disk_count": standalone_disk_count,
        "storage_used_gb": 0.0,
        "ai_insights_used": 0,
        "tasks_count": 0,
        "alert_policies_count": alert_policies_count,
    }


def _empty_usage() -> dict:
    return {
        "organizations_count": 0,
        "users_count": 0,
        "nodes_count": 0,
        "agents_count": 0,
        "proxies_count": 0,
        "gateways_count": 0,
        "source_nas_count": 0,
        "object_storage_count": 0,
        "target_nas_count": 0,
        "standalone_disk_count": 0,
        "storage_used_gb": 0.0,
        "ai_insights_used": 0,
        "tasks_count": 0,
        "alert_policies_count": 0,
    }


def check_quota_available(*, limit: int, current: int, additional: int = 1) -> bool:
    """Return True if within quota. UNLIMITED (-1) always allowed."""
    if limit == UNLIMITED or limit < 0:
        return True
    return (current + additional) <= limit
