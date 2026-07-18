"""Aggregate configuration API routes."""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.configuration.api.urls")),
]
