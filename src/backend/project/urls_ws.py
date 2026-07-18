"""WebSocket URL configuration (ws process).

Composition layer: aggregate per-app WebSocket routes. Only ``apps.node``
exposes external WebSocket surfaces (Agent control plane); other domains use
HTTPS REST under ``/api/v1/...``.
"""

from apps.node.ws.urls import websocket_urlpatterns as node_ws

websocket_urlpatterns = [
    *node_ws,
]

__all__ = ["websocket_urlpatterns"]
