"""Platform Ops system infrastructure APIs."""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.platform import PlatformAuditLogSerializer
from apps.platform_ops.api.views._utils import paginated, safe_int
from apps.platform_ops.selectors.internal.security import list_platform_audit_logs
from apps.platform_ops.selectors.internal.system import (
    migration_status,
    system_health_payload,
    table_row_counts,
)


class PlatformOpsSystemHealthView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        return Response(system_health_payload())


class PlatformOpsSystemDatabaseView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        return Response(
            {
                "table_counts": table_row_counts(),
                "migrations": migration_status(),
            }
        )


class PlatformOpsSystemAuditView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        qs = list_platform_audit_logs(
            search=request.query_params.get("search", ""),
            action=request.query_params.get("action", ""),
        )
        total = qs.count()
        offset = (page - 1) * page_size
        rows = qs[offset : offset + page_size]
        return Response(
            paginated(
                PlatformAuditLogSerializer(rows, many=True).data,
                total=total,
                page=page,
                page_size=page_size,
            )
        )
