from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.permissions_org import IsOrgReader

from apps.alert.api.views._org import require_org
from apps.alert.constants import (
    AVAILABILITY_CHECK_TYPES,
    EVENT_CATEGORIES,
    EVENT_TYPES,
    METRICS_BY_RESOURCE_TYPE,
    SYSTEM_CHECK_TYPES,
    TASK_EVENT_TYPES,
    TASK_TYPES,
    AlertSeverity,
    AlertStatus,
    AlertType,
    ResourceType,
)
from apps.alert.services.internal.metadata_resources import organization_resource_options


def _choices(choice_cls):
    return [{"value": value, "label": label} for value, label in choice_cls.choices]


class MetadataView(APIView):
    permission_classes = [IsAuthenticated, IsOrgReader]

    def get(self, request, kind):
        if kind == "alert-types":
            return Response(_choices(AlertType))
        if kind == "resource-types":
            return Response(_choices(ResourceType))
        if kind == "metrics":
            resource_type = request.query_params.get("resource_type")
            return Response(METRICS_BY_RESOURCE_TYPE.get(resource_type, []))
        if kind == "resources":
            org = require_org(request)
            resource_type = request.query_params.get("resource_type")
            return Response(organization_resource_options(org, resource_type))
        if kind == "task-types":
            return Response(TASK_TYPES)
        if kind == "event-types":
            return Response(
                {
                    "categories": EVENT_CATEGORIES,
                    "types": EVENT_TYPES,
                    "task_event_types": TASK_EVENT_TYPES,
                }
            )
        if kind == "system-check-types":
            return Response(SYSTEM_CHECK_TYPES)
        if kind == "availability-check-types":
            return Response(AVAILABILITY_CHECK_TYPES)
        if kind == "severities":
            return Response(_choices(AlertSeverity))
        if kind == "statuses":
            return Response(_choices(AlertStatus))
        return Response({"detail": "Not found."}, status=404)


class MetadataResourcesView(APIView):
    permission_classes = [IsAuthenticated, IsOrgReader]

    def get(self, request):
        org = require_org(request)
        resource_type = request.query_params.get("resource_type")
        return Response(organization_resource_options(org, resource_type))
