from django.urls import include, path

urlpatterns = [
    path("", include("apps.restore.api.urls")),
]
