"""Platform Ops staff activity API."""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.selectors.internal.security import list_staff_login_events


class PlatformOpsStaffActivityView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        rows = list_staff_login_events(limit=200)
        payload = []
        for row in rows:
            payload.append(
                {
                    "id": row.id,
                    "user_email": row.user.email if row.user_id else "",
                    "organization_key": row.organization.key if row.organization_id else "",
                    "result": row.result,
                    "ip_address": row.ip_address,
                    "created_at": row.created_at,
                }
            )
        return Response({"results": payload})
