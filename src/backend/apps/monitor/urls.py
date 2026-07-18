from django.urls import include, path

urlpatterns = [
    path("", include("apps.monitor.api.urls")),
]
