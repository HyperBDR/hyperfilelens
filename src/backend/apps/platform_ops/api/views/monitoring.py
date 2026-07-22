"""Platform Ops cross-tenant monitoring APIs."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alert.constants import AlertStatus
from apps.alert.models import AlertRecord
from apps.alert.services.internal.lifecycle import resolve_alert
from apps.notification.models import NotificationDelivery
from apps.notification.services.interface import attempt_delivery
from apps.node.services.internal.agent_release import semver_compare
from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.platform import (
    PlatformAlertRowSerializer,
    PlatformNotificationDeliveryRowSerializer,
    PlatformTaskRowSerializer,
)
from apps.platform_ops.api.views._utils import paginated, safe_int
from apps.platform_ops.selectors.internal.health import (
    list_platform_alerts,
    list_platform_notification_deliveries,
    list_platform_nodes,
    list_platform_tasks,
    platform_alert_stats,
    platform_node_stats,
    platform_notification_stats,
    platform_task_stats,
)
from apps.platform_ops.selectors.internal.org_lookup import organization_map
from apps.platform_ops.services.internal.audit import write_platform_audit_log
from apps.task.models import Task
from apps.task.services.interface import cancel_task, retry_task


class _PagedMonitoringView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def _page(
        self,
        request,
        queryset,
        serializer_class,
        *,
        extra_context: dict | None = None,
        extra: dict | None = None,
    ):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        total = queryset.count()
        offset = (page - 1) * page_size
        rows = queryset[offset : offset + page_size]
        context = dict(extra_context or {})
        if serializer_class is PlatformTaskRowSerializer:
            context["org_map"] = organization_map(row.organization_id for row in rows)
        return Response(
            paginated(
                serializer_class(rows, many=True, context=context).data,
                total=total,
                page=page,
                page_size=page_size,
                extra=extra,
            )
        )


class PlatformOpsMonitoringAlertsView(_PagedMonitoringView):
    def get(self, request):
        qs = list_platform_alerts(
            org_key=request.query_params.get("org", ""),
            severity=request.query_params.get("severity", ""),
            status=request.query_params.get("status", ""),
            search=request.query_params.get("search", ""),
        )
        return self._page(
            request,
            qs,
            PlatformAlertRowSerializer,
            extra={"stats": platform_alert_stats()},
        )


class PlatformOpsMonitoringAlertActionView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, alert_id, action):
        alert = get_object_or_404(
            AlertRecord.objects.select_related("organization"),
            id=alert_id,
        )
        note = str(request.data.get("note") or "").strip()[:1000]
        if action == "acknowledge":
            if alert.status != AlertStatus.FIRING:
                return Response({"detail": "Only firing incidents can be acknowledged."}, status=400)
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = request.user.id
            if note:
                alert.metadata = {**(alert.metadata or {}), "acknowledge_note": note}
            alert.save(
                update_fields=[
                    "status",
                    "acknowledged_at",
                    "acknowledged_by",
                    "metadata",
                    "updated_at",
                ]
            )
        elif action == "resolve":
            if alert.status == AlertStatus.RESOLVED:
                return Response({"detail": "Incident is already resolved."}, status=400)
            if note:
                alert.metadata = {**(alert.metadata or {}), "resolve_note": note}
                alert.save(update_fields=["metadata", "updated_at"])
            alert = resolve_alert(alert)
        else:
            return Response({"detail": "Unsupported incident action."}, status=400)
        write_platform_audit_log(
            request=request,
            action=f"monitoring.incident.{action}",
            target_type="alert_record",
            target_id=str(alert.id),
            org_key=alert.organization.key,
            details={"status": alert.status, "note": note},
        )
        return Response(PlatformAlertRowSerializer(alert).data)


class PlatformOpsMonitoringTasksView(_PagedMonitoringView):
    def get(self, request):
        qs = list_platform_tasks(
            org_key=request.query_params.get("org", ""),
            status=request.query_params.get("status", ""),
            task_type=request.query_params.get("task_type", ""),
            search=request.query_params.get("search", ""),
        )
        return self._page(
            request,
            qs,
            PlatformTaskRowSerializer,
            extra={"stats": platform_task_stats()},
        )


class PlatformOpsMonitoringTaskActionView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, task_uuid, action):
        task = get_object_or_404(Task, task_uuid=task_uuid)
        reason = str(request.data.get("reason") or "").strip()[:1000]
        try:
            if action == "cancel":
                task = cancel_task(
                    task_uuid=task.task_uuid,
                    organization_id=task.organization_id,
                    reason=reason or "Task cancelled from Admin Console",
                )
            elif action == "retry":
                task = retry_task(
                    task_uuid=task.task_uuid,
                    organization_id=task.organization_id,
                    reason=reason or "Task retried from Admin Console",
                )
            else:
                return Response({"detail": "Unsupported task action."}, status=400)
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else "Task action failed."
            return Response({"detail": message}, status=400)
        org = organization_map([task.organization_id]).get(task.organization_id, {})
        write_platform_audit_log(
            request=request,
            action=f"monitoring.task.{action}",
            target_type="task",
            target_id=str(task.task_uuid),
            org_key=org.get("key", ""),
            details={"status": task.status, "reason": reason},
        )
        return Response(
            PlatformTaskRowSerializer(
                task,
                context={"org_map": {task.organization_id: org}},
            ).data
        )


class PlatformOpsMonitoringNodesView(_PagedMonitoringView):
    def get(self, request):
        qs = list_platform_nodes(
            org_key=request.query_params.get("org", ""),
            status=request.query_params.get("status", ""),
            role=request.query_params.get("role", ""),
            search=request.query_params.get("search", ""),
        )
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        total = qs.count()
        offset = (page - 1) * page_size
        stats = platform_node_stats()
        latest_version = str(stats.get("latest_version") or "")
        rows = []
        for node in qs[offset : offset + page_size]:
            rows.append(
                {
                    "id": node.id,
                    "organization_id": node.organization_id,
                    "organization_key": node.organization.key,
                    "organization_name": node.organization.name,
                    "hostname": node.name,
                    "role": node.role,
                    "status": node.status,
                    "agent_version": node.version or "",
                    "is_outdated": bool(
                        node.version
                        and latest_version
                        and latest_version != "0.0.0"
                        and semver_compare(node.version, latest_version) < 0
                    ),
                    "os_name": node.os_name or "",
                    "ip_address": str(node.ip_address or ""),
                    "last_seen_at": node.last_seen_at,
                    "metadata": node.metadata or {},
                    "updated_at": node.last_seen_at or node.updated_at,
                }
            )
        return Response(
            paginated(
                rows,
                total=total,
                page=page,
                page_size=page_size,
                extra={"stats": stats},
            )
        )


class PlatformOpsMonitoringNotificationsView(_PagedMonitoringView):
    def get(self, request):
        qs = list_platform_notification_deliveries(
            org_key=request.query_params.get("org", ""),
            status=request.query_params.get("status", ""),
            channel_type=request.query_params.get("channel_type", ""),
            event_type=request.query_params.get("event_type", ""),
            search=request.query_params.get("search", ""),
        )
        return self._page(
            request,
            qs,
            PlatformNotificationDeliveryRowSerializer,
            extra={"stats": platform_notification_stats()},
        )


class PlatformOpsMonitoringNotificationRetryView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, delivery_id):
        with transaction.atomic():
            delivery = get_object_or_404(
                NotificationDelivery.objects.select_for_update().select_related(
                    "organization",
                    "channel",
                ),
                id=delivery_id,
            )
            if delivery.status != NotificationDelivery.Status.FAILED:
                return Response(
                    {"detail": "Only failed deliveries can be retried."},
                    status=400,
                )
            result = attempt_delivery(delivery=delivery)
            write_platform_audit_log(
                request=request,
                action="monitoring.notification.retry",
                target_type="notification_delivery",
                target_id=str(delivery.id),
                org_key=delivery.organization.key,
                details={"status": delivery.status, "delivered": result.ok},
            )
        return Response(
            PlatformNotificationDeliveryRowSerializer(delivery).data,
            status=200 if result.ok else 502,
        )


class PlatformOpsMonitoringHostView(APIView):
    """Control-plane deployment host metrics (container / app server)."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        from apps.monitor.services.interface import build_system_monitor_payload, resolve_monitor_time_range

        since, until, error = resolve_monitor_time_range(
            hours_raw=request.query_params.get("hours"),
            start_at_raw=request.query_params.get("start_at"),
            end_at_raw=request.query_params.get("end_at"),
        )
        if error:
            return Response(error, status=400)
        payload = build_system_monitor_payload(
            since=since,
            until=until,
            host_id=request.query_params.get("host_id"),
        )
        if payload is None:
            return Response({"detail": "Deployment host not found."}, status=404)
        return Response(payload)


class PlatformOpsMonitoringHostsView(APIView):
    """List registered control-plane deployment hosts."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        from apps.monitor.services.interface import list_deployment_hosts

        return Response({"items": list_deployment_hosts()})
