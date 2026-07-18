"""DRF renderers for non-JSON response types."""

from rest_framework.renderers import BaseRenderer


class ServerSentEventsRenderer(BaseRenderer):
    """Allow clients to request ``text/event-stream`` (SSE) without 406."""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data
