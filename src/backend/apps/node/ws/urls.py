"""WebSocket URL routes (Agent control plane)."""

from django.urls import re_path

from apps.node.ws.node_agent import NodeAgentConsumer

websocket_urlpatterns = [
    re_path(r"^ws/node/agent/$", NodeAgentConsumer.as_asgi()),
]
