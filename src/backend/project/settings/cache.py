"""
Django cache configuration (deployment).
"""

from __future__ import annotations

from urllib.parse import urlparse

from .env import build_cache_config, env_str


def _redis_cache_url() -> str:
    explicit = env_str("CACHE_REDIS_URL")
    if explicit:
        return explicit

    broker = env_str("CELERY_BROKER_URL", "redis://redis:6379/0")
    parsed = urlparse(broker)
    return f"{parsed.scheme}://{parsed.netloc}/1"


_CACHE_BACKEND = env_str("CACHE_BACKEND", "redis").lower()

if _CACHE_BACKEND == "redis":
    CACHES = build_cache_config(
        "redis",
        redis_location=_redis_cache_url(),
    )
elif _CACHE_BACKEND == "memcached":
    CACHES = build_cache_config(
        "memcached",
        memcached_location=env_str("CACHE_MEMCACHED_URL", "127.0.0.1:11211"),
    )
elif _CACHE_BACKEND == "database":
    CACHES = build_cache_config("database")
else:
    CACHES = build_cache_config("locmem")

CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = "backend"
