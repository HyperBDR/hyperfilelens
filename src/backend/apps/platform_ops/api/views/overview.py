"""Platform Ops overview API."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.platform import (
    PlatformAlertRowSerializer,
    PlatformTaskRowSerializer,
)
from apps.platform_ops.selectors.internal.health import list_platform_alerts, list_platform_tasks
from apps.platform_ops.selectors.internal.org_lookup import organization_map
from apps.monitor.selectors.internal.platform_summary import platform_monitor_payload


class PlatformOpsOverviewView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        since = timezone.now() - timedelta(hours=24)
        summary = platform_monitor_payload(since=since)
        recent_alerts = list(list_platform_alerts()[:10])
        recent_tasks = list(list_platform_tasks(status="failed")[:10])
        org_map = organization_map(task.organization_id for task in recent_tasks)
        return Response(
            {
                "metrics": {
                    "organizations_active": summary["organizations_active"],
                    "alerts_firing": summary["alerts_firing"],
                    "alerts_acknowledged": summary["alerts_acknowledged"],
                    "tasks_running": summary["tasks_running"],
                    "tasks_failed_24h": summary["tasks_failed_24h"],
                    "tasks_failed_total": summary["tasks_failed_total"],
                    "notifications_failed_total": summary["notifications_failed_total"],
                    "nodes_offline": summary["nodes_offline"],
                },
                "recent_alerts": PlatformAlertRowSerializer(recent_alerts, many=True).data,
                "recent_failed_tasks": PlatformTaskRowSerializer(
                    recent_tasks,
                    many=True,
                    context={"org_map": org_map},
                ).data,
            }
        )
