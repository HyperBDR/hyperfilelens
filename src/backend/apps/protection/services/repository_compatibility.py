from __future__ import annotations

from django.core.exceptions import ValidationError

from apps.source.constants import ResourceType
from apps.source.models import SourceResource
from apps.storage.repositories.models import Repository


def validate_backup_repository_compatible(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
    repository_id: int,
) -> Repository:
    repository = (
        Repository.objects.filter(
            organization_id=organization_id,
            id=repository_id,
            status=Repository.Status.CREATED,
        )
        .first()
    )
    if repository is None:
        raise ValidationError({"repository_id": "Repository not found."})

    if source_type == "nas" and repository.repo_type == Repository.Type.PROXY_FS:
        _validate_proxy_bound_repository(
            organization_id=organization_id,
            source_ref_id=source_ref_id,
            repository=repository,
            nas_message="Local Disk repository is bound to a different proxy node than the NAS source.",
        )
    elif (
        source_type == "nas"
        and
        repository.repo_type == Repository.Type.NAS
        and repository.bind_node_type == Repository.BindNodeType.PROXY
    ):
        _validate_proxy_bound_repository(
            organization_id=organization_id,
            source_ref_id=source_ref_id,
            repository=repository,
            nas_message="NAS repository is bound to a different proxy node than the NAS source.",
        )

    return repository


def _validate_proxy_bound_repository(
    *,
    organization_id: int,
    source_ref_id: int,
    repository: Repository,
    nas_message: str,
) -> None:
    if not repository.bind_node_id:
        raise ValidationError({"repository_id": "Repository is not bound to a proxy node."})

    source_proxy_id = _nas_source_proxy_id(
        organization_id=organization_id,
        source_ref_id=source_ref_id,
    )
    if int(repository.bind_node_id) != source_proxy_id:
        raise ValidationError({"repository_id": nas_message})


def _nas_source_proxy_id(*, organization_id: int, source_ref_id: int) -> int:
    resource = (
        SourceResource.objects.filter(
            organization_id=organization_id,
            resource_type=ResourceType.NAS,
            id=source_ref_id,
            is_deleted=False,
        )
        .select_related("bound_node")
        .first()
    )
    if resource is None:
        raise ValidationError({"source_ref_id": "NAS source not found."})
    if resource.bound_node_id is None:
        raise ValidationError({"source_ref_id": "NAS source is not bound to a proxy node."})
    return int(resource.bound_node_id)
