"""Environment variable helpers for ``project.settings`` submodules."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# src/backend (parent of project/ and common/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def env_str(name: str, default: str = "") -> str:
    """Return a stripped environment variable or *default*."""
    raw = os.getenv(name)
    if raw is None:
        return default
    stripped = raw.strip()
    return stripped if stripped else default


def env_bool(name: str, default: bool = False) -> bool:
    """Return True when the environment variable is a common truthy string."""
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    return raw.strip().lower() in _TRUTHY


def env_int(name: str, default: int) -> int:
    """Parse an integer environment variable, falling back on invalid values."""
    raw = env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    """Parse a float environment variable, falling back on invalid values."""
    raw = env_str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_csv(name: str) -> list[str]:
    """Return a non-empty list of comma-separated, stripped values."""
    raw = env_str(name)
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_cache_config(
    backend: str,
    *,
    redis_location: str | None = None,
    memcached_location: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build Django ``CACHES`` for the selected backend name."""
    defaults: dict[str, Any] = {
        "KEY_PREFIX": "backend",
        "VERSION": 1,
        "TIMEOUT": 300,
    }
    if backend == "redis":
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": redis_location,
                "OPTIONS": {},
                **defaults,
            },
        }
    if backend == "memcached":
        return {
            "default": {
                "BACKEND": (
                    "django.core.cache.backends.memcached.PyMemcacheCache"
                ),
                "LOCATION": memcached_location or "127.0.0.1:11211",
                "OPTIONS": {"no_delay": True, "ignore_exc": True},
                **defaults,
            },
        }
    if backend == "database":
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "LOCATION": "django_cache_table",
                "OPTIONS": {"MAX_ENTRIES": 10000, "CULL_FREQUENCY": 3},
                **defaults,
            },
        }
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "backend-cache",
            "OPTIONS": {"MAX_ENTRIES": 1000, "CULL_FREQUENCY": 3},
            **defaults,
        },
    }
