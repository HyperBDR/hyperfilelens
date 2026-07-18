from django.urls import path

from common.meta.views import DeployProfileView

urlpatterns = [
    path(
        "deploy-profile",
        DeployProfileView.as_view(),
        name="meta-deploy-profile",
    ),
]
