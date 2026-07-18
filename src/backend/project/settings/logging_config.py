"""
Logging configuration (console + optional file).

Set ``LOG_FILE`` to also write Django logs to disk (rotation via logrotate).
"""

from __future__ import annotations

import copy
from typing import Any

from django.utils.log import DEFAULT_LOGGING

from .env import env_str

LOGGING_CONFIG = "logging.config.dictConfig"

LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()
LOG_FILE = env_str("LOG_FILE")

# Defensive cleanup if DEFAULT_LOGGING was mutated by an older deployment.
try:
    _django_server_handler = DEFAULT_LOGGING.get("handlers", {}).get(
        "django.server",
        {},
    )
    _filters = _django_server_handler.get("filters", [])
    if isinstance(_filters, list) and "request_context" in _filters:
        _django_server_handler["filters"] = [
            item for item in _filters if item != "request_context"
        ]
except (AttributeError, KeyError, TypeError):
    pass

_handlers: dict[str, dict[str, Any]] = {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "default",
    },
    "django.server": copy.deepcopy(
        DEFAULT_LOGGING["handlers"]["django.server"],
    ),
}

_root_handlers = ["console"]
if LOG_FILE:
    _handlers["file"] = {
        "class": "logging.FileHandler",
        "formatter": "default",
        "filename": LOG_FILE,
    }
    _root_handlers.append("file")

LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": "common.observability.log_filters.RequestContextFilter",
        },
    },
    "formatters": {
        "default": {
            "()": "common.observability.utc_formatter.UTCISO8601Formatter",
            "format": (
                "[%(asctime)s] [%(levelname)s] [%(hostname)s:%(process)d] "
                "[%(trace_id)s] [%(org_user)s] "
                "[%(service)s(%(filename)s:%(lineno)d)] - %(message)s"
            ),
        },
        "django.server": DEFAULT_LOGGING["formatters"]["django.server"],
    },
    "handlers": _handlers,
    "loggers": {
        "": {"level": LOG_LEVEL, "handlers": _root_handlers},
        "django.server": DEFAULT_LOGGING["loggers"]["django.server"],
        "django.utils.autoreload": {
            "level": "INFO",
            "handlers": _root_handlers,
            "propagate": False,
        },
        "celery": {
            "level": env_str("CELERY_LOG_LEVEL", "INFO").upper(),
            "handlers": _root_handlers,
            "propagate": False,
        },
    },
}

for _handler_name in ("console", "file"):
    _handler = _handlers.get(_handler_name)
    if not _handler:
        continue
    _handler.setdefault("filters", [])
    if "request_context" not in _handler["filters"]:
        _handler["filters"].append("request_context")
