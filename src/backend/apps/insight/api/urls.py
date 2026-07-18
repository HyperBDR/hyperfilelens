from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.insight.api.views import InsightFindingViewSet, InsightReportViewSet, health


router = DefaultRouter()
router.register(r"reports", InsightReportViewSet, basename="insight-report")
router.register(r"findings", InsightFindingViewSet, basename="insight-finding")

urlpatterns = [
    path("health", health, name="insight-health"),
    path("", include(router.urls)),
]

