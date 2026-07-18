from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.audit.constants import AuditAction, AuditResult
from apps.audit.services.interface import write_audit_log
from apps.iam.models import Organization
from apps.node import agent_paths
from apps.node.models import Node
from apps.source.constants import MountStatus, ResourceStatus, ResourceType, SelectableSourceKind
from apps.source.models import SourceResource
from apps.source.selectors.interface import source_resource_by_id, source_resources_queryset
from apps.source.services.internal.connection import (
    apply_connection_test_result,
    mount_resource as _mount_resource,
    schedule_remount_after_proxy_change,
    run_connection_test,
    unmount_resource as _unmount_resource,
)
from apps.source.services.internal.bound_node_rules import validate_bound_node_role
from apps.source.services.internal.nas_path_normalize import normalize_resource_config
from apps.source.services.internal.validators import validate_resource_payload
from apps.source.services.internal.source_pipeline import (
    ensure_pipeline_entry,
    purge_pipeline_entry,
)


def _purge_soft_deleted_name_collision(*, organization_id: int, name: str) -> None:
    """Remove legacy soft-deleted rows that still occupy the org/name unique slot."""
    ghosts = SourceResource.all_objects.filter(
        organization_id=organization_id,
        name=name,
        is_deleted=True,
    )
    for ghost in ghosts:
        if ghost.resource_type == ResourceType.NAS:
            purge_pipeline_entry(
                organization_id=organization_id,
                source_kind=SelectableSourceKind.NAS,
                ref_id=ghost.id,
            )
        ghost.delete()


def _queue_remount_after_proxy_binding(
    *,
    resource: SourceResource,
    old_node_id: int | None,
) -> None:
    resource.mount_status = MountStatus.UNMOUNTED
    resource.mount_point = ""
    resource.mount_error = ""
    resource.save(
        update_fields=["mount_status", "mount_point", "mount_error", "updated_at"]
    )
    schedule_remount_after_proxy_change(
        resource_id=resource.id,
        old_node_id=old_node_id,
    )


@transaction.atomic
def create_source_resource(
    *,
    organization: Organization,
    user,
    name: str,
    resource_type: str,
    config: dict | None = None,
    credentials: dict | None = None,
    bound_node_id: int | None = None,
    description: str = "",
    status: str | None = None,
) -> SourceResource:
    config = normalize_resource_config(resource_type, config or {})
    credentials = credentials or {}
    validate_resource_payload(
        resource_type=resource_type,
        config=config,
        credentials=credentials,
    )
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Name is required.")
    _purge_soft_deleted_name_collision(
        organization_id=organization.id,
        name=normalized_name,
    )
    if source_resources_queryset(organization_id=organization.id).filter(name=normalized_name).exists():
        raise ValueError("A source resource with this name already exists.")

    node = None
    if bound_node_id:
        node = Node.objects.filter(id=bound_node_id, organization_id=organization.id).first()
        if node is None:
            raise ValueError("Bound node not found in this organization.")
        validate_bound_node_role(resource_type=resource_type, node=node)

    try:
        resource = SourceResource.objects.create(
            organization=organization,
            name=normalized_name,
            description=description or "",
            resource_type=resource_type,
            config=config or {},
            credentials=credentials or {},
            bound_node=node,
            status=status or ResourceStatus.ACTIVE,
            created_by=user if user and user.is_authenticated else None,
        )
    except IntegrityError as exc:
        raise ValueError("A source resource with this name already exists.") from exc
    if resource_type == ResourceType.NAS:
        mount_path = str((config or {}).get("path") or "").strip()
        if mount_path:
            resource.mount_point = agent_paths.require_agent_mount_path(mount_path)
            resource.save(update_fields=["mount_point"])
        ensure_pipeline_entry(
            organization_id=organization.id,
            source_kind=SelectableSourceKind.NAS,
            ref_id=resource.id,
        )
    write_audit_log(
        organization=organization,
        user=user,
        action=AuditAction.CREATE,
        resource_type="source_resource",
        resource_id=str(resource.id),
        resource_name=resource.name,
        result=AuditResult.SUCCESS,
    )
    if resource.resource_type in ResourceType.REQUIRES_MOUNT:
        try_probe_resource_capacity(resource)
    return resource


def try_probe_resource_capacity(resource: SourceResource) -> dict | None:
    """Best-effort NAS/NFS/CIFS capacity probe when a bound proxy is online."""
    if resource.resource_type not in ResourceType.REQUIRES_MOUNT:
        return None
    node = resource.bound_node
    if node is None and resource.bound_node_id:
        node = Node.objects.filter(id=resource.bound_node_id).first()
    if node is None or node.status != Node.Status.ONLINE:
        return None
    result = run_connection_test(resource=resource)
    apply_connection_test_result(resource, result)
    return result


@transaction.atomic
def update_source_resource(
    *,
    resource: SourceResource,
    user,
    **fields,
) -> SourceResource:
    if set(fields.keys()) <= {"bound_node", "bound_node_id"}:
        node_id = fields.get("bound_node_id") or fields.get("bound_node")
        if node_id is not None and int(node_id) == resource.bound_node_id:
            return resource

    if "name" in fields and fields["name"]:
        name = str(fields["name"]).strip()
        if (
            source_resources_queryset(organization_id=resource.organization_id)
            .filter(name=name)
            .exclude(id=resource.id)
            .exists()
        ):
            raise ValueError("A source resource with this name already exists.")
        resource.name = name
    if "description" in fields:
        resource.description = fields["description"] or ""
    if "resource_type" in fields and fields["resource_type"]:
        resource.resource_type = fields["resource_type"]
    if "config" in fields:
        resource.config = {**(resource.config or {}), **(fields["config"] or {})}
        resource.config = normalize_resource_config(resource.resource_type, resource.config)
    if "credentials" in fields:
        incoming = fields["credentials"] or {}
        merged = {**(resource.credentials or {})}
        for key, val in incoming.items():
            if val not in (None, ""):
                merged[key] = val
        resource.credentials = merged
    if "bound_node" in fields or "bound_node_id" in fields:
        node_id = fields.get("bound_node_id") or fields.get("bound_node")
        old_bound_node_id = resource.bound_node_id
        if node_id:
            node = Node.objects.filter(
                id=int(node_id),
                organization_id=resource.organization_id,
                is_deleted=False,
            ).first()
            if node is None:
                raise ValueError("Bound node not found.")
            validate_bound_node_role(resource_type=resource.resource_type, node=node)
            if node.status != Node.Status.ONLINE:
                raise ValueError(f'Node "{node.name}" is not online.')
            resource.bound_node = node
            bound_node_changed = old_bound_node_id != node.id
        else:
            # Source NAS resources must always stay bound to a Proxy.
            from apps.source.constants import ResourceType as _RT
            if resource.resource_type in (_RT.NAS, _RT.NFS, _RT.CIFS):
                raise ValueError(
                    "Cannot unbind proxy. Replace the proxy instead."
                )
            resource.bound_node = None
            bound_node_changed = old_bound_node_id is not None
    else:
        bound_node_changed = False
        old_bound_node_id = resource.bound_node_id
    if "status" in fields and fields["status"]:
        resource.status = fields["status"]

    validate_resource_payload(
        resource_type=resource.resource_type,
        config=resource.config,
        credentials=resource.credentials,
    )
    resource.save()
    if bound_node_changed and resource.resource_type in ResourceType.REQUIRES_MOUNT and resource.bound_node:
        _queue_remount_after_proxy_binding(
            resource=resource,
            old_node_id=old_bound_node_id,
        )
    write_audit_log(
        organization=resource.organization,
        user=user,
        action=AuditAction.UPDATE,
        resource_type="source_resource",
        resource_id=str(resource.id),
        resource_name=resource.name,
        result=AuditResult.SUCCESS,
    )
    return resource


def delete_source_resource(*, resource: SourceResource, user, force: bool = False) -> dict:
    from apps.source.services.internal.backup_source_delete import (
        BackupSourceDeleteFailed,
        delete_backup_sources,
    )

    selectable_id = f"nas:{resource.id}"
    try:
        result = delete_backup_sources(
            org=resource.organization,
            ids=[selectable_id],
            force=force,
            user=user,
        )
    except BackupSourceDeleteFailed as exc:
        return {
            "deleted": False,
            "ok": False,
            "message": exc.message,
            "reasons": [reason.as_dict() for reason in exc.reasons],
            "hint": exc.hint,
            "agent_removal": None,
        }

    deleted = selectable_id in result.get("deleted", [])
    return {
        "deleted": deleted,
        "ok": result.get("ok", deleted),
        "result": result.get("result"),
        "warnings": result.get("warnings", []),
        "agent_removal": None,
    }


def test_resource_connection(*, resource: SourceResource) -> dict:
    result = run_connection_test(resource=resource)
    apply_connection_test_result(resource, result)
    return result


def test_draft_connection(
    *,
    organization_id: int,
    bound_node_id: int,
    resource_type: str,
    config: dict | None = None,
    credentials: dict | None = None,
) -> dict:
    node = Node.objects.filter(id=bound_node_id, organization_id=organization_id).first()
    if node is None:
        return {"success": False, "message": "Node not found."}
    try:
        validate_bound_node_role(resource_type=resource_type, node=node)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}
    return run_connection_test(
        bound_node=node,
        resource_type=resource_type,
        config=config,
        credentials=credentials,
    )


@transaction.atomic
def bind_node(*, resource: SourceResource, node_id: int) -> dict:
    node = Node.objects.filter(
        id=node_id,
        organization_id=resource.organization_id,
        is_deleted=False,
    ).first()
    if node is None:
        return {"success": False, "message": "Node not found."}
    try:
        validate_bound_node_role(resource_type=resource.resource_type, node=node)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}
    if node.status != Node.Status.ONLINE:
        return {"success": False, "message": f'Node "{node.name}" is not online.'}
    old_bound_node_id = resource.bound_node_id
    resource.bound_node = node
    resource.save(update_fields=["bound_node", "updated_at"])
    if resource.resource_type in ResourceType.REQUIRES_MOUNT:
        _queue_remount_after_proxy_binding(
            resource=resource,
            old_node_id=old_bound_node_id,
        )
    return {
        "success": True,
        "message": f'Resource bound to node "{node.name}".',
        "bound_node": {"id": node.id, "name": node.name, "status": node.status},
    }


def unbind_node(*, resource: SourceResource) -> dict:
    from apps.source.constants import ResourceType as _RT
    if resource.resource_type in (_RT.NAS, _RT.NFS, _RT.CIFS):
        return {
            "success": False,
            "message": "Cannot unbind proxy. Replace the proxy instead.",
        }
    resource.bound_node = None
    resource.mount_status = "unmounted"
    resource.mount_point = ""
    resource.mount_error = ""
    resource.save(
        update_fields=["bound_node", "mount_status", "mount_point", "mount_error", "updated_at"]
    )
    return {"success": True, "message": "Resource unbound."}


def resource_statistics(*, organization_id: int) -> dict:
    qs = source_resources_queryset(organization_id=organization_id)
    by_type = {}
    for code, _ in SourceResource._meta.get_field("resource_type").choices:
        by_type[code] = qs.filter(resource_type=code).count()
    agg = SourceResource.objects.filter(
        organization_id=organization_id,
        is_deleted=False,
    ).aggregate(total_size=Sum("total_size"), total_files=Sum("file_count"))
    return {
        "total": qs.count(),
        "active": qs.filter(status="active").count(),
        "inactive": qs.filter(status="inactive").count(),
        "error": qs.filter(status="error").count(),
        "mounted": qs.filter(mount_status="mounted").count(),
        "by_type": by_type,
        "total_size": int(agg["total_size"] or 0),
        "total_files": int(agg["total_files"] or 0),
    }


def get_resource(*, organization_id: int, resource_id: int) -> SourceResource | None:
    return source_resource_by_id(organization_id=organization_id, resource_id=resource_id)


def mount_resource(*, resource: SourceResource) -> dict:
    return _mount_resource(resource)


def unmount_resource(*, resource: SourceResource) -> dict:
    return _unmount_resource(resource)
