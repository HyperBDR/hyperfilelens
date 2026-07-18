from django.http import JsonResponse

from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

from apps.iam.permissions_org import IsOrgStaffReader, IsOrgWriter
from apps.insight.models import InsightFinding, InsightReport
from apps.insight.api.serializers import InsightFindingSerializer, InsightReportSerializer
from common.drf.org_scoped import OrgScopedMixin


def health(_request):
    return JsonResponse({"app": "insight", "status": "ok"})


class InsightReportViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    queryset = InsightReport.objects.select_related(
        "organization",
        "snapshot",
        "snapshot__source_snapshot",
    ).all()
    serializer_class = InsightReportSerializer
    permission_classes = [IsAuthenticated, IsOrgWriter]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return super().get_permissions()


class InsightFindingViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    queryset = InsightFinding.objects.select_related(
        "organization",
        "snapshot",
        "snapshot__source_snapshot",
        "report",
    ).all()
    serializer_class = InsightFindingSerializer
    permission_classes = [IsAuthenticated, IsOrgWriter]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return super().get_permissions()
