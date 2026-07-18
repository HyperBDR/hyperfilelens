from django.urls import include, path

urlpatterns = [
    path("", include("apps.lens_bridge.api.urls")),
]
