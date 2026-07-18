from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.notification.api.views import NotificationChannelViewSet, NotificationLogViewSet
from apps.notification.api.views.health import health


router = DefaultRouter()
router.register(r"channels", NotificationChannelViewSet, basename="notification-channel")
router.register(r"logs", NotificationLogViewSet, basename="notification-log")

urlpatterns = [
    path("health", health, name="notification-health"),
    path("", include(router.urls)),
]
