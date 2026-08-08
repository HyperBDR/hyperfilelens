"""Platform AI model routes under ``/api/v1/platform-ops/lens/`` (Host essential)."""

from django.urls import path

from apps.instance_settings.api.views.lens_models import (
    PlatformOpsLensModelProxyView,
    PlatformOpsLensSettingsView,
)

urlpatterns = [
    path("models", PlatformOpsLensModelProxyView.as_view(), name="platform-ops-lens-models-list"),
    path("settings", PlatformOpsLensSettingsView.as_view(), name="platform-ops-lens-settings"),
    path(
        "models/providers",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-providers",
    ),
    path(
        "models/catalog",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-catalog",
    ),
    path("models/test", PlatformOpsLensModelProxyView.as_view(), name="platform-ops-lens-models-test"),
    path(
        "models/<uuid:config_uuid>",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-detail",
    ),
    path(
        "models/<uuid:config_uuid>/test-call",
        PlatformOpsLensModelProxyView.as_view(),
        name="platform-ops-lens-models-test-call",
    ),
]
