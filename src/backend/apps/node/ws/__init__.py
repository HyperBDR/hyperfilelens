"""
Agent WebSocket package (``/ws/node/agent/``).

Flat layout: ``urls`` / ``node_agent`` / ``wire`` / session helpers.
"""

from .urls import websocket_urlpatterns

__all__ = ["websocket_urlpatterns"]
