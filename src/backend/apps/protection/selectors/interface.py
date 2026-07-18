from __future__ import annotations

from django.db.models import CharField, Q, QuerySet
from django.db.models.functions import Cast

from apps.protection.models import BackupPolicy, FileFilterRule

ALLOWED_ORDERING = {"created_at", "-created_at", "name", "-name", "updated_at", "-updated_at"}


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _ordering(value: str | None) -> list[str]:
    if value in ALLOWED_ORDERING:
        return [value or "-created_at", "-id"]
    return ["-created_at", "-id"]


def backup_policies_queryset(*, organization_id: int) -> QuerySet[BackupPolicy]:
    return BackupPolicy.objects.filter(organization_id=organization_id)


def filter_backup_policies(
    queryset: QuerySet[BackupPolicy],
    *,
    search: str | None = None,
    search_field: str | None = None,
    is_active: str | None = None,
    ordering: str | None = None,
) -> QuerySet[BackupPolicy]:
    state = _parse_bool(is_active)
    if state is not None:
        queryset = queryset.filter(is_active=state)
    query = (search or "").strip()
    if query:
        if (search_field or "").strip().lower() == "name":
            return queryset.filter(name__icontains=query).order_by(*_ordering(ordering))
        lowered = query.lower()
        status_q = Q()
        if lowered in {"active", "enabled", "on"}:
            status_q = Q(is_active=True)
        elif lowered in {"disabled", "inactive", "off"}:
            status_q = Q(is_active=False)
        queryset = queryset.annotate(
            schedule_text=Cast("schedule", CharField()),
            retention_text=Cast("retention", CharField()),
        ).filter(
            Q(name__icontains=query)
            | Q(schedule_text__icontains=query)
            | Q(retention_text__icontains=query)
            | status_q
        )
    return queryset.order_by(*_ordering(ordering))


def get_backup_policy(*, organization_id: int, policy_id: int) -> BackupPolicy | None:
    return backup_policies_queryset(organization_id=organization_id).filter(pk=policy_id).first()


def policy_display_name(*, policy_id: int, organization_id: int | None = None) -> str:
    queryset = BackupPolicy.objects.filter(pk=policy_id)
    if organization_id is not None:
        queryset = queryset.filter(organization_id=organization_id)
    return str(queryset.values_list("name", flat=True).first() or "").strip()


def file_filter_rules_queryset(*, organization_id: int) -> QuerySet[FileFilterRule]:
    return FileFilterRule.objects.filter(organization_id=organization_id)


def filter_file_filter_rules(
    queryset: QuerySet[FileFilterRule],
    *,
    search: str | None = None,
    search_field: str | None = None,
    is_active: str | None = None,
    ordering: str | None = None,
) -> QuerySet[FileFilterRule]:
    state = _parse_bool(is_active)
    if state is not None:
        queryset = queryset.filter(is_active=state)
    query = (search or "").strip()
    if query:
        if (search_field or "").strip().lower() == "name":
            return queryset.filter(name__icontains=query).order_by(*_ordering(ordering))
        lowered = query.lower()
        status_q = Q()
        if lowered in {"active", "enabled", "on"}:
            status_q = Q(is_active=True)
        elif lowered in {"disabled", "inactive", "off"}:
            status_q = Q(is_active=False)
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(ignore_patterns__icontains=query)
            | status_q
        )
    return queryset.order_by(*_ordering(ordering))


def get_file_filter_rule(*, organization_id: int, rule_id: int) -> FileFilterRule | None:
    return file_filter_rules_queryset(organization_id=organization_id).filter(pk=rule_id).first()


__all__ = [
    "backup_policies_queryset",
    "file_filter_rules_queryset",
    "filter_backup_policies",
    "filter_file_filter_rules",
    "get_backup_policy",
    "get_file_filter_rule",
    "policy_display_name",
]
