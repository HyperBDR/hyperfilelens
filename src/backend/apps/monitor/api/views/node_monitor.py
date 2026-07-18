"""REST: tenant node host monitor dashboard."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.org_context import require_org
from apps.iam.permissions_org import IsOrgStaffReader
from apps.monitor.services.internal.node_monitor import (
    build_node_monitor_payload,
    list_monitor_nodes,
    resource_type_for_role,
)
from apps.monitor.services.interface import resolve_monitor_time_range
from apps.node.models import Node


class NodeMonitorListView(APIView):
    """
    GET /api/v1/monitors/nodes/

    Query: role=agent|proxy|gateway (optional).
    """

    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get(self, request):
        org = require_org(request)
        role = str(request.query_params.get("role") or "").strip() or None
        nodes = list_monitor_nodes(organization_id=org.id, role=role)
        items = []
        for node in nodes:
            meta = node.metadata if isinstance(node.metadata, dict) else {}
            inventory = meta.get("inventory") if isinstance(meta.get("inventory"), dict) else {}
            hostname = str(inventory.get("hostname") or node.name or node.id)
            platform = " ".join(
                p
                for p in (str(inventory.get("os") or ""), str(inventory.get("arch") or ""))
                if p
            )
            items.append(
                {
                    "id": node.id,
                    "name": node.name,
                    "role": node.role,
                    "status": node.status,
                    "hostname": hostname,
                    "platform": platform,
                    "resource_type": resource_type_for_role(node.role),
                    "last_seen_at": node.last_seen_at.isoformat() if node.last_seen_at else None,
                }
            )
        return Response({"items": items})


class NodeMonitorDetailView(APIView):
    """
    GET /api/v1/monitors/nodes/<node_id>/

    Returns host info, current snapshot, and time series for charts.
    """

    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get(self, request, node_id: int):
        org = require_org(request)
        node = Node.objects.filter(pk=node_id, organization_id=org.id).first()
        if node is None:
            return Response({"error": "node not found"}, status=404)

        since, until, error = resolve_monitor_time_range(
            hours_raw=request.query_params.get("hours"),
            start_at_raw=request.query_params.get("start_at"),
            end_at_raw=request.query_params.get("end_at"),
        )
        if error:
            return Response(error, status=400)

        payload = build_node_monitor_payload(node=node, since=since, until=until)
        return Response(payload)
