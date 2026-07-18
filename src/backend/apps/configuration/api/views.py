"""
Configuration center REST API (platform admin).
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.configuration.api.permissions import PLATFORM_CONFIG_PERMISSIONS
from apps.configuration.api.serializers import (
    ConfigKeySpecSerializer,
    GlobalConfigListSerializer,
    GlobalConfigSerializer,
)
from apps.configuration.models import GlobalConfig
from apps.configuration.selectors.interface import list_registry_specs
from apps.configuration.services.tenant_settings import (
    list_org_settings,
    upsert_org_settings,
)
from apps.iam.permissions_org import IsOrgAdmin, get_membership, resolve_org_key


@extend_schema_view(
    list=extend_schema(tags=["configuration"]),
    retrieve=extend_schema(tags=["configuration"]),
    create=extend_schema(tags=["configuration"]),
    update=extend_schema(tags=["configuration"]),
    partial_update=extend_schema(tags=["configuration"]),
    destroy=extend_schema(tags=["configuration"]),
)
class GlobalConfigViewSet(viewsets.ModelViewSet):
    queryset = GlobalConfig.objects.all()
    permission_classes = PLATFORM_CONFIG_PERMISSIONS

    def get_serializer_class(self):
        if self.action == "list":
            return GlobalConfigListSerializer
        return GlobalConfigSerializer

    def get_queryset(self):
        queryset = GlobalConfig.objects.all()
        category = self.request.query_params.get("category")
        scope = self.request.query_params.get("scope")
        tenant_key = self.request.query_params.get("tenant_key")
        is_active = self.request.query_params.get("is_active")
        config_key = self.request.query_params.get("key")

        if category:
            queryset = queryset.filter(category=category)
        if scope:
            queryset = queryset.filter(scope=scope)
        if tenant_key is not None:
            queryset = queryset.filter(tenant_key=tenant_key)
        if is_active is not None:
            queryset = queryset.filter(is_active=str(is_active).lower() == "true")
        if config_key:
            queryset = queryset.filter(key=config_key)
        return queryset.order_by("category", "key", "scope", "tenant_key")

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @extend_schema(
        tags=["configuration"],
        responses=ConfigKeySpecSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="registry")
    def registry(self, request):
        specs = list_registry_specs()
        payload = ConfigKeySpecSerializer(specs, many=True).data
        return Response(payload)

class OrgSettingsView(APIView):
    """
    GET/PATCH /api/v1/configuration/org-settings/

    Organization-scoped settings for Configuration → System Settings.
    Requires X-Org-Key and Owner/Admin membership.
    """

    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def _org_key(self, request) -> str | None:
        membership = get_membership(request)
        if membership is None:
            return None
        org_key = resolve_org_key(request) or membership.organization.key
        if org_key != membership.organization.key:
            return None
        return org_key

    def get(self, request):
        org_key = self._org_key(request)
        if not org_key:
            return Response(
                {"detail": "Valid organization context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "org_key": org_key,
                "settings": list_org_settings(org_key=org_key),
            }
        )

    def patch(self, request):
        org_key = self._org_key(request)
        if not org_key:
            return Response(
                {"detail": "Valid organization context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        items = request.data.get("settings")
        if not isinstance(items, list) or not items:
            return Response(
                {"detail": "settings array is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            settings = upsert_org_settings(
                org_key=org_key,
                user=request.user,
                items=items,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"org_key": org_key, "settings": settings})
