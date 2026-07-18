"""HTTP URL entry for the node app (includes ``api/urls``)."""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.node.api.urls")),
]
