"""
Legacy URL mount for admin UI compatibility.

Deprecated: prefer ``/api/v1/configuration/configs/``.
"""

from rest_framework.routers import DefaultRouter

from apps.configuration.api.views import GlobalConfigViewSet


legacy_router = DefaultRouter()
legacy_router.register(r"", GlobalConfigViewSet, basename="configuration-config-legacy")

urlpatterns = legacy_router.urls
