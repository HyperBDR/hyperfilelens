"""
Scene-related views.
"""

import logging

from django.utils.translation import gettext_lazy as _

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.http.public_api import AnonymousPublicViewMixin


logger = logging.getLogger(__name__)


class SceneSerializer:
    """
    Lightweight schema-only placeholder.
    """


class GetAvailableScenesView(AnonymousPublicViewMixin, APIView):

    @extend_schema(
        tags=["auth"],
        summary=_("Get available scenes"),
        parameters=[
            OpenApiParameter(
                name="language",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=_("Language code"),
                required=False,
            )
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        try:
            scenes = [
                {
                    "key": "default",
                    "name": "Default",
                    "description": "Default usage scene",
                }
            ]
            return Response(scenes, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.error("Failed to get scenes: %s", exc, exc_info=True)
            return Response(
                {"success": False, "error": _("Failed to retrieve scenes")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

