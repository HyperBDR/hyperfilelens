"""Configuration API routes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.configuration.api.views import GlobalConfigViewSet, OrgSettingsView


router = DefaultRouter()
router.register(r"configs", GlobalConfigViewSet, basename="configuration-config")

urlpatterns = [
    path("org-settings/", OrgSettingsView.as_view(), name="configuration-org-settings"),
    path("", include(router.urls)),
]
