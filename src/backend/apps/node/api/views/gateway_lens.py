"""Gateway LensNode config for enrolled data gateways (sidecar install)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.models import Organization
from apps.lens_bridge.services import provisioning
from apps.node.api import permissions as node_permissions
from apps.node.models import Node
from apps.node.models.base import NodeRole


class GatewayLensConfigView(APIView):
    """
    Return SourceLens LensNode credentials for an enrolled gateway.

    Auth: ``X-Org-Key`` + ``X-Node-Token`` (same as heartbeat).
    Query: ``node_id`` (required after first registration).
    """

    permission_classes = [node_permissions.AllowAny]

    def get(self, request: Request) -> Response:
        org_key = str(request.headers.get("X-Org-Key", "") or "").strip()
        node_token = str(request.headers.get("X-Node-Token", "") or "").strip()
        node_id_raw = str(request.query_params.get("node_id") or "").strip()

        if not org_key or not node_token or not node_id_raw:
            return Response(
                {"error": "X-Org-Key, X-Node-Token, and node_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            node_id = int(node_id_raw)
        except ValueError:
            return Response({"error": "invalid node_id"}, status=status.HTTP_400_BAD_REQUEST)

        org = Organization.objects.filter(key=org_key, is_active=True).first()
        if org is None:
            return Response({"error": "organization not found"}, status=status.HTTP_404_NOT_FOUND)

        node = Node.objects.filter(
            organization=org,
            pk=node_id,
            role=NodeRole.GATEWAY,
            is_deleted=False,
        ).first()
        if node is None:
            return Response({"error": "gateway not found"}, status=status.HTTP_404_NOT_FOUND)

        lens = provisioning.provision_gateway_lens_on_register(org=org, gateway=node)
        if lens is None:
            return Response(
                {"error": "SourceLens bridge is not configured or lens provisioning failed"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not lens.get("lensnode_token"):
            return Response(
                {"error": "LensNode token unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"node_id": node.id, "lens": lens})
