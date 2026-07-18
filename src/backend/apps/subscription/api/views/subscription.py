from django.http import JsonResponse

from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

from apps.iam.permissions_org import IsOrgStaffReader, IsOrgWriter
from apps.subscription.models import (
    Entitlement,
    OrganizationSubscription,
    Plan,
    Quota,
    UsageCounter,
)
from apps.subscription.api.serializers import (
    EntitlementSerializer,
    OrganizationSubscriptionSerializer,
    PlanSerializer,
    QuotaSerializer,
    UsageCounterSerializer,
)
from common.drf.org_scoped import OrgScopedMixin


def health(_request):
    return JsonResponse({"app": "subscription", "status": "ok"})


class PlanViewSet(viewsets.ModelViewSet):
    """Global plan catalog (not tenant-scoped)."""

    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]


class OrganizationSubscriptionViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    queryset = OrganizationSubscription.objects.select_related("organization", "plan").all()
    serializer_class = OrganizationSubscriptionSerializer
    org_lookup_field = "organization_id"
    permission_classes = [IsAuthenticated, IsOrgWriter]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return super().get_permissions()


class EntitlementViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    queryset = Entitlement.objects.select_related("organization").all()
    serializer_class = EntitlementSerializer
    org_lookup_field = "organization_id"
    permission_classes = [IsAuthenticated, IsOrgWriter]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return super().get_permissions()


class QuotaViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    queryset = Quota.objects.select_related("organization").all()
    serializer_class = QuotaSerializer
    org_lookup_field = "organization_id"
    permission_classes = [IsAuthenticated, IsOrgWriter]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return super().get_permissions()


class UsageCounterViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    queryset = UsageCounter.objects.select_related("organization").all()
    serializer_class = UsageCounterSerializer
    org_lookup_field = "organization_id"
    permission_classes = [IsAuthenticated, IsOrgWriter]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return super().get_permissions()
