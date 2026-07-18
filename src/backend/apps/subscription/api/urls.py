from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.subscription.api.views import (
    EntitlementViewSet,
    LicenseViewSet,
    OrganizationSubscriptionViewSet,
    PlanViewSet,
    QuotaViewSet,
    UsageCounterViewSet,
    health,
)


router = DefaultRouter()
router.register(r"plans", PlanViewSet, basename="plan")
router.register(r"organizations", OrganizationSubscriptionViewSet, basename="organization-subscription")
router.register(r"entitlements", EntitlementViewSet, basename="entitlement")
router.register(r"quotas", QuotaViewSet, basename="quota")
router.register(r"usage", UsageCounterViewSet, basename="usage")
router.register(r"licenses", LicenseViewSet, basename="license")

urlpatterns = [
    path("health", health, name="subscription-health"),
    path("", include(router.urls)),
]
