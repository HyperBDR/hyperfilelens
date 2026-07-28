from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.storage.repositories.views import RepositoryViewSet
from apps.storage.repositories.views import RepositoryTaskCancelView
from apps.storage.repositories.views import health as repositories_health
from apps.storage.provider_catalog.views import StorageProviderCatalogView


router = DefaultRouter()
router.register(r"repositories", RepositoryViewSet, basename="repository")

repository_validate_s3 = RepositoryViewSet.as_view({"post": "validate_s3"})

urlpatterns = [
    path("health", repositories_health, name="storage-health"),
    path(
        "repository-tasks/<uuid:task_uuid>/cancel/",
        RepositoryTaskCancelView.as_view(),
        name="repository-task-cancel",
    ),
    path(
        "provider-catalog/",
        StorageProviderCatalogView.as_view(),
        name="storage-provider-catalog",
    ),
    path(
        "repositories/validate/s3",
        repository_validate_s3,
        name="repository-validate-s3-no-slash",
    ),
    path("", include(router.urls)),
]
