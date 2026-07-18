from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.iam.views import (
    health,
    MembershipViewSet,
    OrganizationViewSet,
    PersonalApiKeyViewSet,
)


router = DefaultRouter()
router.register(r"orgs", OrganizationViewSet, basename="org")
router.register(r"memberships", MembershipViewSet, basename="membership")
router.register(r"api-keys", PersonalApiKeyViewSet, basename="api-key")

urlpatterns = [
    path("health", health, name="iam-health"),
    path("", include(router.urls)),
]

