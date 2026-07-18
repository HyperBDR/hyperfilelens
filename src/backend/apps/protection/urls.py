from django.urls import include, path

urlpatterns = [
    path("", include("apps.protection.api.urls")),
]

