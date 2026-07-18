from django.urls import include, path

from apps.notification.stream_views import stream_health

urlpatterns = [
    path("stream/health", stream_health, name="notification-stream-health"),
    path("", include("apps.notification.api.urls")),
]
