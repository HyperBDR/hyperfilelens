"""Runtime tunables for configuration infrastructure."""

import os

from apps.configuration import conf

CONFIG_KEY_CACHE_TTL = "configuration.cache.ttl_seconds"


def get_cache_ttl_seconds() -> int:
    raw = os.getenv("CONFIG_CACHE_TTL_SECONDS", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return conf.DEFAULT_CACHE_TTL_SECONDS
