"""ASGI application for HTTP API only (api process / Gunicorn+Uvicorn / runserver).

Routes: ``project.urls_http``. WebSocket: ``project.asgi_ws`` + ``project.urls_ws``.
"""

from django.core.asgi import get_asgi_application

from project import configure_django

configure_django()

_django_app = get_asgi_application()


async def application(scope, receive, send):
    """HTTP ASGI app; absorb Uvicorn lifespan events Django does not handle."""
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
        return
    await _django_app(scope, receive, send)
