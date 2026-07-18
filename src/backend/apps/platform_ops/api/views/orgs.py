"""Platform Ops organization API."""

from __future__ import annotations

from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.orgs import (
    PlatformOpsOrganizationDetailSerializer,
    PlatformOpsOrganizationListSerializer,
)
from apps.platform_ops.api.serializers.platform import (
    PlatformOrgCreateSerializer,
    PlatformOrgUpdateSerializer,
)
from apps.platform_ops.api.views._utils import paginated, safe_int
from apps.platform_ops.selectors.internal.org_summary import organization_resource_summary
from apps.platform_ops.selectors.internal.orgs import get_organization_detail, list_organizations
from apps.platform_ops.services.internal.orgs import (
    create_platform_organization,
    delete_platform_organization,
    update_platform_organization,
)


class PlatformOpsOrganizationListView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20)
        search = request.query_params.get("search", "")

        qs = list_organizations(search=search)
        total = qs.count()
        offset = (page - 1) * page_size
        page_qs = qs[offset : offset + page_size]
        data = PlatformOpsOrganizationListSerializer(page_qs, many=True).data
        return Response(paginated(data, total=total, page=page, page_size=page_size))

    def post(self, request):
        serializer = PlatformOrgCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            org = create_platform_organization(
                request=request,
                key=payload["key"],
                name=payload["name"],
                owner_user_id=payload["owner_user_id"],
                is_active=payload.get("is_active", True),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        detail = get_organization_detail(org_id=org.pk)
        return Response(
            PlatformOpsOrganizationDetailSerializer(detail).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformOpsOrganizationDetailView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, org_id: int):
        org = get_organization_detail(org_id=org_id)
        if org is None:
            raise Http404
        return Response(PlatformOpsOrganizationDetailSerializer(org).data)

    def patch(self, request, org_id: int):
        org = get_organization_detail(org_id=org_id)
        if org is None:
            raise Http404
        serializer = PlatformOrgUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated = update_platform_organization(org, request=request, **serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        detail = get_organization_detail(org_id=updated.pk)
        return Response(PlatformOpsOrganizationDetailSerializer(detail).data)

    def delete(self, request, org_id: int):
        org = get_organization_detail(org_id=org_id)
        if org is None:
            raise Http404
        delete_platform_organization(org=org, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformOpsOrganizationSummaryView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, org_id: int):
        org = get_organization_detail(org_id=org_id)
        if org is None:
            raise Http404
        return Response(organization_resource_summary(org))
