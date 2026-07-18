"""DRF renderers for the platform HTTP response envelope."""

from rest_framework import status
from rest_framework.renderers import JSONRenderer

from common.http.constants import FAILED_MESSAGE, SUCCESS_CODE, SUCCESS_MESSAGE


class CustomJSONRenderer(JSONRenderer):
    """Wrap successful responses as ``{code, message, data}``."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            return super().render(
                data,
                accepted_media_type=accepted_media_type,
                renderer_context=None,
            )

        response = renderer_context.get("response")
        if response is None:
            return super().render(
                data,
                accepted_media_type=accepted_media_type,
                renderer_context=renderer_context,
            )

        if response.status_code == status.HTTP_204_NO_CONTENT:
            return b""

        is_success = status.HTTP_200_OK <= response.status_code < 300

        if not isinstance(data, dict):
            data = {"data": data}

        code = data.get("code", SUCCESS_CODE if is_success else response.status_code)
        message = data.get(
            "message",
            SUCCESS_MESSAGE if is_success else FAILED_MESSAGE,
        )
        formatted = {
            "code": code,
            "message": message,
            "data": data.get("data", data),
        }
        return super().render(
            formatted,
            accepted_media_type=accepted_media_type,
            renderer_context=renderer_context,
        )
