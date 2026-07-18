"""Cross-tenant health queries for Platform Ops."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.alert.constants import AlertStatus
from apps.alert.models import AlertRecord
from apps.notification.constants import NotificationLogStatus
from apps.notification.models import NotificationLog
from apps.platform_ops.selectors.internal.org_lookup import (
    organization_ids_for_key,
    organization_ids_matching,
)
from apps.task.models import Task


def list_platform_alerts(
    *,
    org_key: str = "",
    severity: str = "",
    status: str = "",
    search: str = "",
) -> QuerySet:
    qs = AlertRecord.objects.select_related("organization").order_by(
        "-last_triggered_at",
        "-created_at",
    )
    if org_key:
        qs = qs.filter(organization__key=org_key)
    if severity:
        qs = qs.filter(severity=severity)
    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(status__in=[AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED])
    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(title__icontains=term)
            | Q(message__icontains=term)
            | Q(resource_name__icontains=term)
            | Q(organization__key__icontains=term)
            | Q(organization__name__icontains=term)
        )
    return qs


def list_platform_tasks(
    *,
    org_key: str = "",
    status: str = "",
    task_type: str = "",
    search: str = "",
) -> QuerySet:
    qs = Task.objects.order_by("-finished_at", "-updated_at", "-id")
    if org_key:
        org_ids = organization_ids_for_key(org_key)
        qs = qs.filter(organization_id__in=org_ids or [-1])
    if status:
        qs = qs.filter(status=status)
    if task_type:
        qs = qs.filter(task_type=task_type)
    term = (search or "").strip()
    if term:
        org_ids = organization_ids_matching(term)
        qs = qs.filter(
            Q(display_name__icontains=term)
            | Q(error_message__icontains=term)
            | Q(organization_id__in=org_ids)
        )
    return qs


def list_platform_nodes(*, org_key: str = "", status: str = "", role: str = "") -> QuerySet:
    from apps.node.models import Node

    qs = Node.objects.select_related("organization").order_by("-updated_at", "-id")
    if org_key:
        qs = qs.filter(organization__key=org_key)
    if status:
        qs = qs.filter(status=status)
    if role:
        qs = qs.filter(role=role)
    return qs


def list_platform_notification_failures(*, org_key: str = "", search: str = "") -> QuerySet:
    qs = (
        NotificationLog.objects.filter(status=NotificationLogStatus.FAILED)
        .select_related("organization", "channel")
        .order_by("-sent_at", "-id")
    )
    if org_key:
        qs = qs.filter(organization__key=org_key)
    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(error_message__icontains=term)
            | Q(organization__key__icontains=term)
            | Q(organization__name__icontains=term)
            | Q(channel__name__icontains=term)
        )
    return qs
