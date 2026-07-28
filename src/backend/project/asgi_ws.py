"""ASGI application for WebSocket only (ws process / Daphne on :8001).

Routes: ``project.urls_ws``. HTTP: ``project.asgi_http`` + ``project.urls_http``.
"""

import logging

from django.core.asgi import get_asgi_application

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

from project import configure_django

logger = logging.getLogger(__name__)


def _build_application():
    from project.urls_ws import websocket_urlpatterns

    return ProtocolTypeRouter(
        {
            "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        }
    )


def _clear_stale_ws_routes() -> None:
    from apps.node.services.internal.redis_store import clear_ws_instance_routes

    try:
        summary = clear_ws_instance_routes()
    except Exception:
        logger.warning("failed to clear stale websocket routes on startup", exc_info=True)
        return
    if summary.get("agent_locations_deleted") or summary.get("ws_alive_deleted"):
        logger.info("cleared stale websocket routes on startup: %s", summary)


def _start_ws_recovery_window() -> None:
    from apps.node.services.internal.redis_store import begin_ws_recovery_hold
    from apps.node.ws.lifecycle import ensure_ws_instance_keepalive_started

    try:
        begin_ws_recovery_hold()
    except Exception:
        logger.warning("failed to start websocket recovery hold", exc_info=True)
    ensure_ws_instance_keepalive_started()


configure_django()
# Initialise Django before Channels routing (registers apps and settings).
_django_asgi = get_asgi_application()
_clear_stale_ws_routes()
_start_ws_recovery_window()

application = _build_application()
