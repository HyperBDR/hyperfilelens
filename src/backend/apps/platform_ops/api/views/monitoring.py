"""Platform Ops cross-tenant monitoring APIs."""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.platform import (
    PlatformAlertRowSerializer,
    PlatformNotificationRowSerializer,
    PlatformTaskRowSerializer,
)
from apps.platform_ops.api.views._utils import paginated, safe_int
from apps.platform_ops.selectors.internal.health import (
    list_platform_alerts,
    list_platform_notification_failures,
    list_platform_nodes,
    list_platform_tasks,
)
from apps.platform_ops.selectors.internal.org_lookup import organization_map


class _PagedMonitoringView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def _page(self, request, queryset, serializer_class, *, extra_context: dict | None = None):
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
        return self._page(request, qs, PlatformAlertRowSerializer)


class PlatformOpsMonitoringTasksView(_PagedMonitoringView):
    def get(self, request):
        qs = list_platform_tasks(
            org_key=request.query_params.get("org", ""),
            status=request.query_params.get("status", ""),
            task_type=request.query_params.get("task_type", ""),
            search=request.query_params.get("search", ""),
        )
        return self._page(request, qs, PlatformTaskRowSerializer)


class PlatformOpsMonitoringNodesView(_PagedMonitoringView):
    def get(self, request):
        qs = list_platform_nodes(
            org_key=request.query_params.get("org", ""),
            status=request.query_params.get("status", ""),
            role=request.query_params.get("role", ""),
        )
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        total = qs.count()
        offset = (page - 1) * page_size
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
                    "updated_at": node.last_seen_at or node.updated_at,
                }
            )
        return Response(paginated(rows, total=total, page=page, page_size=page_size))


class PlatformOpsMonitoringNotificationsView(_PagedMonitoringView):
    def get(self, request):
        qs = list_platform_notification_failures(
            org_key=request.query_params.get("org", ""),
            search=request.query_params.get("search", ""),
        )
        return self._page(request, qs, PlatformNotificationRowSerializer)


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
