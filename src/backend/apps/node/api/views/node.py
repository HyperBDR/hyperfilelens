"""REST views for ``Node`` lifecycle."""

import logging

from django.http import JsonResponse
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services.interface import write_audit_log
from apps.iam.models import Organization
from apps.node.api import permissions as node_permissions
from apps.node.api.serializers import (
    NodeHeartbeatSerializer,
    NodeSerializer,
)
from apps.node.api.serializers.node_operation import NodeOperationStartSerializer
from apps.node.api.serializers.lifecycle_watch import (
    NodeLifecycleWatchEntrySerializer,
    NodeLifecycleWatchRequestSerializer,
)
from apps.node.api.views.node_operation import _lifecycle_error_response
from common.drf.org_scoped import OrgScopedMixin
from apps.node.api.views.mixins import SoftDeleteDestroyMixin
from apps.node.api.pagination import NodePagination
from apps.node.api.views.enrollment_helpers import get_valid_enrollment_token
from apps.node.models import Node, NodeToken
from apps.node.models.base import NodeRole
from apps.node.selectors.internal.node_query import node_field_search_q, node_search_q
from apps.monitor.services.internal.node_metrics import ingest_node_heartbeat_metrics
from apps.node.selectors.interface import list_nodes
from apps.node.services.internal.node_lifecycle import (
    LIFECYCLE_KIND_UPGRADE,
    enrich_node_row,
    start_node_remove,
    start_node_upgrade,
)
from apps.node.services.internal.node_naming import (
    is_auto_assigned_node_name,
    resolve_registration_node_name,
    uniquify_node_name,
)
from apps.node.services.internal.local_platform_gateway import registration_metadata
from apps.node.exceptions import NodeLifecycleError
from apps.node.services.internal.agent_uninstall import ProxyHasBoundResources
from apps.node.services.internal.bindings import collect_proxy_bindings
from apps.node.services.internal.client_ip import resolve_agent_client_ip
from apps.source.services.internal.agent_host_sync import sync_agent_source_host

logger = logging.getLogger(__name__)


def health(_request):
    return JsonResponse({"app": "node", "status": "ok"})


class NodeViewSet(OrgScopedMixin, SoftDeleteDestroyMixin, viewsets.ModelViewSet):
    org_scoped_skip_actions = ("heartbeat",)

    serializer_class = NodeSerializer
    permission_classes = [
        node_permissions.IsAuthenticated,
        node_permissions.IsOrgWriter,
    ]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [
                node_permissions.IsAuthenticated(),
                node_permissions.IsOrgStaffReader(),
            ]
        if self.action == "lifecycle_watch":
            return [
                node_permissions.IsAuthenticated(),
                node_permissions.IsOrgOperator(),
            ]
        if self.action == "heartbeat":
            return [node_permissions.AllowAny()]
        if self.action == "operations":
            return [
                node_permissions.IsAuthenticated(),
                node_permissions.IsOrgOperator(),
            ]
        return super().get_permissions()

    def get_org_scoped_queryset(self):
        queryset = Node.objects.select_related("organization").all()
        role = (self.request.query_params.get("role") or "").strip()
        if role:
            queryset = queryset.filter(role=role)
        status = (self.request.query_params.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by("name", "id")

    def _build_enrichments(self, nodes) -> dict[int, dict]:
        enrichments: dict[int, dict] = {}
        for node in nodes:
            enrichments[node.id] = enrich_node_row(
                org=self.org,
                node=node,
                user=self.request.user,
            )
        return enrichments

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self, "_node_enrichments", None) is not None:
            context["enrichments"] = self._node_enrichments
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        search = (request.query_params.get("search") or "").strip()
        search_field = (request.query_params.get("search_field") or "").strip()
        if search:
            field_query = node_field_search_q(search_field, search) if search_field else None
            queryset = queryset.filter(field_query or node_search_q(search))

        page_size_raw = request.query_params.get("page_size")
        if page_size_raw is not None:
            paginator = NodePagination()
            page = paginator.paginate_queryset(queryset, request, view=self)
            nodes = list(page) if page is not None else []
            self._node_enrichments = self._build_enrichments(nodes)
            serializer = self.get_serializer(nodes, many=True)
            if page is not None:
                return paginator.get_paginated_response(serializer.data)

        nodes = list(queryset)
        self._node_enrichments = self._build_enrichments(nodes)
        serializer = self.get_serializer(nodes, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        self._node_enrichments = self._build_enrichments([instance])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="lifecycle-watch")
    def lifecycle_watch(self, request):
        """Poll lifecycle state for in-flight upgrade/remove batches (read-only)."""
        ser = NodeLifecycleWatchRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        node_ids = ser.validated_data["node_ids"]
        nodes = list(
            self.get_org_scoped_queryset().filter(pk__in=node_ids).order_by("id"),
        )
        payload = NodeLifecycleWatchEntrySerializer(
            nodes,
            many=True,
            context={"org": self.org},
        ).data
        return Response({"nodes": payload})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.role not in (NodeRole.AGENT, NodeRole.PROXY, NodeRole.GATEWAY):
            return super().destroy(request, *args, **kwargs)
        try:
            result = start_node_remove(
                org=instance.organization,
                node=instance,
                user=request.user,
            )
        except NodeLifecycleError as exc:
            if exc.code == "proxy_has_bindings":
                bindings = collect_proxy_bindings(
                    organization_id=instance.organization_id,
                    proxy_id=instance.id,
                )
                return Response(
                    {
                        "detail": str(exc),
                        "bound": bindings.totals,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ProxyHasBoundResources as exc:
            return Response(
                {
                    "detail": "Proxy has bound resources. Replace them before deletion.",
                    "bound": exc.bindings.totals,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result.get("state") != "completed":
            return Response(
                {
                    "detail": "Node removal is asynchronous. Use POST /nodes/{id}/operations/.",
                    "operation": result,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance: Node) -> None:
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="operations")
    def operations(self, request, pk=None):
        node = self.get_object()
        ser = NodeOperationStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        kind = ser.validated_data["kind"]
        try:
            if kind == LIFECYCLE_KIND_UPGRADE:
                result = start_node_upgrade(org=self.org, node=node, user=request.user)
            else:
                result = start_node_remove(
                    org=self.org,
                    node=node,
                    user=request.user,
                    force=bool(ser.validated_data.get("force")),
                )
        except Exception as exc:
            return _lifecycle_error_response(exc)

        write_audit_log(
            organization=self.org,
            user=request.user,
            action=f"node.lifecycle.{kind}",
            target_type="node",
            target_id=str(node.id),
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=str(request.META.get("HTTP_USER_AGENT", "") or ""),
            metadata={
                "kind": kind,
                "role": node.role,
                "operation_id": result.get("operation_id"),
                "task_id": result.get("task_id"),
                "state": result.get("state"),
            },
        )
        return Response(result, status=status.HTTP_202_ACCEPTED)

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[node_permissions.IsOrgStaffReader],
    )
    def bindings(self, request, pk=None):
        """Return the resources bound to this node as a Proxy worker.

        Empty when the node is not a Proxy.
        """
        node = self.get_object()
        from apps.node.services.internal.bindings import collect_proxy_bindings
        return Response(
            collect_proxy_bindings(
                organization_id=node.organization_id,
                proxy_id=node.id,
            ).to_payload()
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[node_permissions.AllowAny],
    )
    def heartbeat(self, request):
        org_key = str(request.headers.get("X-Org-Key", "") or "").strip()
        node_token = str(request.headers.get("X-Node-Token", "") or "").strip()
        if not org_key:
            return Response(
                {"error": "X-Org-Key required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org = Organization.objects.filter(key=org_key, is_active=True).first()
        if org is None:
            return Response(
                {"error": "organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = NodeHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        client_ip = resolve_agent_client_ip(request)

        node_id = payload.get("node_id")
        node = None
        token_row = None
        if node_id:
            node = list_nodes(organization=org).filter(pk=node_id).first()

        if node is None and node_token:
            token_row = get_valid_enrollment_token(
                org=org,
                token=node_token,
                role=payload["role"],
            )
            if token_row is None:
                return Response(
                    {"error": "invalid enrollment token"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            node = Node.objects.create(
                organization=org,
                name=uniquify_node_name(
                    organization_id=org.id,
                    name=resolve_registration_node_name(payload=payload),
                ),
                role=payload["role"],
                version=payload.get("version", ""),
                os_name=payload.get("os_name", ""),
                metadata=registration_metadata(
                    payload.get("metadata"),
                    token_note=token_row.note,
                ),
                last_seen_at=timezone.now(),
                ip_address=client_ip,
            )
            unique_name = uniquify_node_name(
                organization_id=org.id,
                name=node.name,
                exclude_node_id=node.id,
            )
            if unique_name != node.name:
                node.name = unique_name
                node.save(update_fields=["name", "updated_at"])
            NodeToken.objects.filter(pk=token_row.pk).update(used_at=timezone.now())
        elif node is not None:
            node.last_seen_at = timezone.now()
            if is_auto_assigned_node_name(node.name):
                next_name = resolve_registration_node_name(
                    payload=payload,
                    fallback=node.name,
                )
                next_name = uniquify_node_name(
                    organization_id=org.id,
                    name=next_name,
                    exclude_node_id=node.id,
                )
                if next_name != node.name:
                    node.name = next_name
            elif payload.get("name"):
                node.name = payload.get("name")
            node.version = payload.get("version", node.version)
            node.os_name = payload.get("os_name", node.os_name)
            if "metadata" in payload:
                node.metadata = registration_metadata(
                    payload.get("metadata"),
                    existing_metadata=node.metadata,
                )
            if client_ip:
                node.ip_address = client_ip
            node.save()
        else:
            return Response(
                {"error": "node not found; enrollment token required"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            ingest_node_heartbeat_metrics(node=node)
        except Exception:
            logger.warning("node heartbeat metrics ingest failed node_id=%s", node.id, exc_info=True)

        try:
            sync_agent_source_host(node=node)
        except Exception:
            logger.warning("node heartbeat source-host sync failed node_id=%s", node.id, exc_info=True)

        payload: dict = {"node_id": node.id, "status": node.status}
        if node.role == NodeRole.GATEWAY:
            from apps.lens_bridge.services import provisioning

            lens = provisioning.provision_gateway_lens_on_register(
                org=org,
                gateway=node,
                owner_user=token_row.created_by if token_row is not None else None,
                scope=token_row.gateway_scope if token_row is not None else "",
            )
            if lens:
                payload["lens"] = lens

        return Response(payload)
