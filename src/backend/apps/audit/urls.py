from django.urls import include, path

urlpatterns = [
    path("", include("apps.audit.api.urls")),
]

