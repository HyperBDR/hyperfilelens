from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.alert.api.views import (
    AlertPolicyViewSet,
    AlertRecordViewSet,
    MetadataResourcesView,
    MetadataView,
)

router = DefaultRouter()
router.register(r"policies", AlertPolicyViewSet, basename="alert-policy")
router.register(r"records", AlertRecordViewSet, basename="alert-record")

urlpatterns = [
    path("metadata/<str:kind>/", MetadataView.as_view(), name="alert-metadata"),
    path("metadata/resources/", MetadataResourcesView.as_view(), name="alert-metadata-resources"),
    path("", include(router.urls)),
]
