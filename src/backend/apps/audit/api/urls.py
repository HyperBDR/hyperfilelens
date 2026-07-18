from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.audit.api.views import AuditLogViewSet


router = DefaultRouter()
router.register(r"", AuditLogViewSet, basename="audit")

urlpatterns = [path("", include(router.urls))]

