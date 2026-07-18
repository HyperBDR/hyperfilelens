from django.urls import include, path

urlpatterns = [
    path("", include("apps.source.api.urls")),
]
