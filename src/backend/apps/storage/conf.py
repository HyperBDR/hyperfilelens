"""Storage defaults and runtime settings."""

import os

from django.core.exceptions import ImproperlyConfigured


CONFIG_KEY_RETENTION = "backup.retention.default"
CONFIG_KEY_FILTERS = "backup.filters.default"

DEFAULT_RETENTION = {
    "type": "gfs",
    "daily": 7,
    "weekly": 4,
    "monthly": 12,
}

DEFAULT_FILTERS = {
    "exclude": ["/tmp", "/var/cache"],
    "include": [],
}


REPOSITORY_HEALTH_INTERVAL_ENV = "STORAGE_REPOSITORY_HEALTH_INTERVAL_SECONDS"
DEFAULT_REPOSITORY_HEALTH_INTERVAL_SECONDS = 300
MIN_REPOSITORY_HEALTH_INTERVAL_SECONDS = 60


def repository_health_interval_seconds() -> int:
    raw = os.getenv(
        REPOSITORY_HEALTH_INTERVAL_ENV,
        str(DEFAULT_REPOSITORY_HEALTH_INTERVAL_SECONDS),
    ).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"{REPOSITORY_HEALTH_INTERVAL_ENV} must be an integer."
        ) from exc
    if value < MIN_REPOSITORY_HEALTH_INTERVAL_SECONDS:
        raise ImproperlyConfigured(
            f"{REPOSITORY_HEALTH_INTERVAL_ENV} must be at least "
            f"{MIN_REPOSITORY_HEALTH_INTERVAL_SECONDS} seconds."
        )
    return value
