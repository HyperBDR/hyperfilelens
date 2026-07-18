"""
Deployment and reverse-proxy hardening (Django ``SECURE_*``, cookie flags).

``TRUSTED_PROXY`` defaults to on when ``FRONTEND_URL`` uses HTTPS (nginx TLS
termination). Set ``TRUSTED_PROXY=false`` to bypass when debugging api directly.

Not for content moderation; use ``common.security`` for runtime input checks.
"""

from .env import env_bool, env_csv, env_int, env_str

SESSION_COOKIE_NAME = "hfl_sessionid"
CSRF_COOKIE_NAME = "hfl_csrftoken"

_DEBUG = env_bool("DJANGO_DEBUG")
_FRONTEND_URL = env_str("FRONTEND_URL", "http://localhost:3000")
_TRUSTED_PROXY = env_bool("TRUSTED_PROXY", default=_FRONTEND_URL.startswith("https://"))

if _TRUSTED_PROXY:
    SECURE_PROXY_SSL_HEADER = (
        env_str("SECURE_PROXY_SSL_HEADER", "HTTP_X_FORWARDED_PROTO"),
        env_str("SECURE_PROXY_SSL_VALUE", "https").lower(),
    )
    USE_X_FORWARDED_HOST = True

if env_bool("SECURE_SSL_REDIRECT"):
    SECURE_SSL_REDIRECT = True

if env_str("SECURE_HSTS_SECONDS"):
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0)

if env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS"):
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
if env_bool("SECURE_HSTS_PRELOAD"):
    SECURE_HSTS_PRELOAD = True

if env_bool("SESSION_COOKIE_SECURE"):
    SESSION_COOKIE_SECURE = True
elif not _DEBUG:
    SESSION_COOKIE_SECURE = True

if env_bool("CSRF_COOKIE_SECURE"):
    CSRF_COOKIE_SECURE = True
elif not _DEBUG:
    CSRF_COOKIE_SECURE = True

_csrf_origins = env_csv("CSRF_TRUSTED_ORIGINS")
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = _csrf_origins
elif _DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
