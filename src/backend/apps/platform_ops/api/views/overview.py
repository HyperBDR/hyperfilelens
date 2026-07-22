"""Platform Ops overview API."""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.selectors.internal.overview import (
    normalize_range_hours,
    platform_overview_payload,
)


class PlatformOpsOverviewView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        hours = normalize_range_hours(request.query_params.get("hours"))
        return Response(platform_overview_payload(hours=hours))
