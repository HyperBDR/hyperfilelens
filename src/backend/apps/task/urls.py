from django.urls import include, path

urlpatterns = [
    path("", include("apps.task.api.urls")),
]
