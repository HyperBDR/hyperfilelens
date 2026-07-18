from __future__ import annotations

from django.db.models import QuerySet

from apps.restore.models import RestorePlan, RestoreRecord


def restore_plans_queryset(*, organization_id: int) -> QuerySet[RestorePlan]:
    return RestorePlan.objects.filter(organization_id=organization_id)


def filter_restore_plans(
    queryset: QuerySet[RestorePlan],
    *,
    backup_config_id: int | None = None,
    source_type: str | None = None,
    source_ref_id: int | None = None,
    enabled: bool | None = None,
) -> QuerySet[RestorePlan]:
    if backup_config_id is not None:
        queryset = queryset.filter(backup_config_id=backup_config_id)
    if source_type:
        queryset = queryset.filter(source_type=source_type)
    if source_ref_id is not None:
        queryset = queryset.filter(source_ref_id=source_ref_id)
    if enabled is not None:
        queryset = queryset.filter(enabled=enabled)
    return queryset.order_by("source_type", "source_ref_id", "sort_order", "id")


def get_restore_plan(*, organization_id: int, plan_id: int) -> RestorePlan | None:
    return RestorePlan.objects.filter(organization_id=organization_id, pk=plan_id).first()


def restore_records_queryset(*, organization_id: int) -> QuerySet[RestoreRecord]:
    return (
        RestoreRecord.objects.filter(organization_id=organization_id)
        .prefetch_related("items")
        .order_by("-created_at", "-id")
    )


def filter_restore_records(
    queryset: QuerySet[RestoreRecord],
    *,
    source_type: str | None = None,
    source_ref_id: int | None = None,
    task_uuid: str | None = None,
    search: str | None = None,
) -> QuerySet[RestoreRecord]:
    if source_type:
        queryset = queryset.filter(source_type=source_type)
    if source_ref_id is not None:
        queryset = queryset.filter(source_ref_id=source_ref_id)
    if task_uuid:
        queryset = queryset.filter(task_uuid=task_uuid)
    query = (search or "").strip()
    if query:
        queryset = queryset.filter(restore_uid__icontains=query)
    return queryset


def get_restore_record(*, organization_id: int, record_id: int) -> RestoreRecord | None:
    return restore_records_queryset(organization_id=organization_id).filter(pk=record_id).first()


__all__ = [
    "filter_restore_plans",
    "filter_restore_records",
    "get_restore_plan",
    "get_restore_record",
    "restore_plans_queryset",
    "restore_records_queryset",
]
