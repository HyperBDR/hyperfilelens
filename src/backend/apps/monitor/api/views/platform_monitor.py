"""Cross-tenant ops summary for platform administrators."""

from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.configuration.api.permissions import IsPlatformConfigAdmin
from apps.monitor.selectors.internal.platform_summary import platform_monitor_payload


def _serialize_alert(row) -> dict:
    return {
        "id": str(row.id),
        "organization_id": row.organization_id,
        "title": row.title,
        "severity": row.severity,
        "status": row.status,
        "resource_type": row.resource_type,
        "resource_name": row.resource_name,
        "last_triggered_at": (
            row.last_triggered_at.isoformat() if row.last_triggered_at else None
        ),
    }


def _serialize_task(row) -> dict:
    return {
        "id": row.id,
        "task_uuid": str(row.task_uuid),
        "organization_id": row.organization_id,
        "task_type": row.task_type,
        "status": row.status,
        "display_name": row.display_name,
        "error_message": (row.error_message or "")[:200],
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


class PlatformMonitorView(APIView):
    """
    GET /api/v1/monitors/platform/

    Aggregated health counters for operations console (staff only).
    """

    permission_classes = [IsAuthenticated, IsPlatformConfigAdmin]

    def get(self, request):
        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        summary = platform_monitor_payload(since=since_24h)

        return Response(
            {
                "scope": "platform",
                "organizations_active": summary["organizations_active"],
                "alerts_firing": summary["alerts_firing"],
                "alerts_acknowledged": summary["alerts_acknowledged"],
                "tasks_running": summary["tasks_running"],
                "tasks_failed_24h": summary["tasks_failed_24h"],
                "tasks_failed_total": summary["tasks_failed_total"],
                "notifications_failed_total": summary["notifications_failed_total"],
                "nodes_offline": summary["nodes_offline"],
                "recent_alerts": [
                    _serialize_alert(row) for row in summary["recent_alerts"]
                ],
                "recent_failed_tasks": [
                    _serialize_task(row) for row in summary["recent_failed_tasks"]
                ],
            }
        )
