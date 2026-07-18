"""Composition root for the Django project package.

Wiring:
  ``project/settings/`` — Django configuration (``DJANGO_SETTINGS_MODULE``)
  ``project/urls_http`` / ``urls_ws`` — HTTP and WebSocket route composition
  ``project/asgi_http`` / ``asgi_ws`` — ASGI entrypoints

Process split (same ``api`` container in Compose):
  HTTP API (:8000): Gunicorn + ``urls_http`` + ``asgi_http``
  WebSocket (:8001): Daphne + ``urls_ws`` + ``asgi_ws``
"""

import os

DJANGO_SETTINGS_MODULE = "project.settings"

__all__ = ["DJANGO_SETTINGS_MODULE", "configure_django"]


def configure_django() -> None:
    """Set default settings module if not already configured."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)
