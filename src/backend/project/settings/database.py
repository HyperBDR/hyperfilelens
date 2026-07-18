"""
Database settings (deployment).
"""

from __future__ import annotations

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .env import env_str

DATABASE_URL = env_str("DATABASE_URL")
DB_ENGINE = env_str("DB_ENGINE").lower()

if DB_ENGINE and DB_ENGINE not in {"postgres", "postgresql", "pgsql"}:
    raise ImproperlyConfigured(
        "HyperFileLens supports PostgreSQL only; DB_ENGINE must be postgresql."
    )

if not DATABASE_URL:
    db_user = env_str("POSTGRES_USER", "postgres")
    db_password = env_str("POSTGRES_PASSWORD", "postgres")
    db_host = env_str("POSTGRES_HOST", "localhost")
    db_port = env_str("POSTGRES_PORT", "5432")
    db_name = env_str("POSTGRES_DB", "hyperfilelens")
    DATABASE_URL = (
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )


def _build_default_db_config(url: str) -> dict[str, object]:
    config = dj_database_url.parse(url, conn_max_age=0)
    if config["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured(
            "HyperFileLens supports PostgreSQL only; DATABASE_URL must use "
            "the postgresql:// scheme."
        )
    options = dict(config.get("OPTIONS") or {})
    options.setdefault("connect_timeout", 60)
    options.setdefault("options", "-c statement_timeout=300000")
    config["OPTIONS"] = options
    return config


DATABASES = {"default": _build_default_db_config(DATABASE_URL)}
