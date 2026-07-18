from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from apps.protection.models import BackupConfig

ALLOWED_ORDERING = {"created_at", "-created_at", "name", "-name", "updated_at", "-updated_at"}


def _ordering(value: str | None) -> list[str]:
    if value in ALLOWED_ORDERING:
        return [value or "-created_at", "-id"]
    return ["-created_at", "-id"]


def backup_configs_queryset(*, organization_id: int) -> QuerySet[BackupConfig]:
    return BackupConfig.objects.filter(organization_id=organization_id).annotate(
        _directory_count=Count("directories"),
    )


def filter_backup_configs(
    queryset: QuerySet[BackupConfig],
    *,
    search: str | None = None,
    source_type: str | None = None,
    repository_id: int | None = None,
    ordering: str | None = None,
) -> QuerySet[BackupConfig]:
    if source_type:
        queryset = queryset.filter(source_type=source_type)
    if repository_id is not None:
        queryset = queryset.filter(repository_id=repository_id)
    query = (search or "").strip()
    if query:
        queryset = queryset.filter(Q(name__icontains=query))
    return queryset.order_by(*_ordering(ordering))


def get_backup_config(*, organization_id: int, config_id: int) -> BackupConfig | None:
    return backup_configs_queryset(organization_id=organization_id).filter(pk=config_id).first()


__all__ = [
    "backup_configs_queryset",
    "filter_backup_configs",
    "get_backup_config",
]
