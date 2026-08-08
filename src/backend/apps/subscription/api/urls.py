"""OSS subscription URLs: license + health always; governance only when EE is on."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.subscription.api.views import LicenseViewSet, health
from common.extension_loader import extensions_enabled

router = DefaultRouter()
router.register(r"licenses", LicenseViewSet, basename="license")

urlpatterns = [
    path("health", health, name="subscription-health"),
    path("", include(router.urls)),
]

if extensions_enabled():
    urlpatterns.append(
        path("", include("apps.subscription.api.governance_urls")),
    )
