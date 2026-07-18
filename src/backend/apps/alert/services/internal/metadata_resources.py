"""Resource picker options for alert policies."""

from __future__ import annotations

from apps.alert.constants import ResourceType
from apps.iam.models import Organization
from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.storage.repositories.models import Repository
from apps.task.models import Task


def _option(item_id, name: str, status: str = "active") -> dict:
    return {"id": str(item_id), "name": name, "status": status}


def resource_options(*, organization_id: int, resource_type: str | None) -> list[dict]:
    if not resource_type:
        return []
    if resource_type == ResourceType.SYSTEM:
        return [
            {
                "id": "00000000-0000-0000-0000-000000000000",
                "name": "Control Plane",
                "status": "active",
            }
        ]
    if resource_type == ResourceType.SYNC_PROXY:
        qs = Node.objects.filter(
            organization_id=organization_id, role=NodeRole.PROXY
        )
        return [_option(n.id, n.name, n.status) for n in qs.order_by("name")[:300]]
    if resource_type == ResourceType.AGENT_PROXY:
        qs = Node.objects.filter(
            organization_id=organization_id, role=NodeRole.AGENT
        )
        return [_option(n.id, n.name, n.status) for n in qs.order_by("name")[:300]]
    if resource_type == ResourceType.GATEWAY:
        qs = Node.objects.filter(
            organization_id=organization_id, role=NodeRole.GATEWAY
        )
        return [_option(n.id, n.name, n.status) for n in qs.order_by("name")[:300]]
    if resource_type in (
        ResourceType.BACKUP_REPOSITORY,
        ResourceType.TARGET_STORAGE,
    ):
        qs = Repository.objects.filter(organization_id=organization_id)
        return [
            _option(r.id, r.name, getattr(r, "status", "active") or "active")
            for r in qs.order_by("name")[:300]
        ]
    if resource_type == ResourceType.TASK:
        qs = Task.objects.filter(organization_id=organization_id)
        return [
            _option(j.task_uuid, f"{j.task_type} / {j.display_name}", j.status)
            for j in qs.order_by("-created_at", "-id")[:300]
        ]
    if resource_type == ResourceType.USER:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return [
            _option(
                u.id,
                getattr(u, "email", None) or str(u.id),
                "active" if u.is_active else "inactive",
            )
            for u in User.objects.order_by("email")[:300]
        ]
    if resource_type == ResourceType.SOURCE_RESOURCE:
        try:
            from apps.source.models import SourceResource

            return [
                _option(r.id, r.name, r.status)
                for r in SourceResource.objects.filter(organization_id=organization_id).order_by(
                    "name"
                )[:300]
            ]
        except Exception:
            return []
    return []


def organization_resource_options(org: Organization, resource_type: str | None) -> list[dict]:
    return resource_options(organization_id=org.id, resource_type=resource_type)
