from django.urls import include, path

urlpatterns = [
    path("", include("apps.alert.api.urls")),
]

