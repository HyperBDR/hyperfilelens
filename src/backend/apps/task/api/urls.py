from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.task.api.views import TaskViewSet, health


router = DefaultRouter()
router.register(r"", TaskViewSet, basename="task")

urlpatterns = [
    path("health", health, name="task-health"),
    path("", include(router.urls)),
]
