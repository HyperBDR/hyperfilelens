"""
Django REST Framework, JWT, and cookie authentication (deployment).
"""

from datetime import timedelta

from .env import env_bool, env_int, env_str

_SECRET_KEY = env_str("SECRET_KEY", "dev-only-change-me")
_COOKIE_SECURE = env_bool("COOKIE_SECURE", default=True)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.iam.auth.authentication.JWTAuthenticationFromCookies",
        # JWT cookie SPA only — do not add SessionAuthentication (requires CSRF on POST/DELETE).
        # Personal API keys: apps.iam.auth.personal_api_key.PersonalApiKeyAuthentication
        # (implemented, not enabled — add here when exposing API-key console access)
    ),
    "DEFAULT_PAGINATION_CLASS": "common.http.pagination.APIPagination",
    "PAGE_SIZE": env_int("API_PAGE_SIZE", 10),
    "DEFAULT_RENDERER_CLASSES": (
        "common.http.renders.CustomJSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
    ),
    "EXCEPTION_HANDLER": "common.http.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

if env_bool("ENABLE_THROTTLING"):
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = (
        "common.http.throttling.OrgScopedRateThrottle",
    )
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        "org": env_str("THROTTLE_ORG_RATE", "600/min"),
    }

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        hours=env_int("JWT_ACCESS_TOKEN_HOURS", 1),
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        hours=env_int("JWT_REFRESH_TOKEN_HOURS", 24),
    ),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env_str("SIMPLE_JWT_SIGNING_KEY", _SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

COOKIE_AUTH = {
    "ACCESS_TOKEN_COOKIE_NAME": "access_token",
    "REFRESH_TOKEN_COOKIE_NAME": "refresh_token",
    "ACCESS_TOKEN_COOKIE_HTTPONLY": True,
    "REFRESH_TOKEN_COOKIE_HTTPONLY": True,
    "ACCESS_TOKEN_COOKIE_SECURE": _COOKIE_SECURE,
    "REFRESH_TOKEN_COOKIE_SECURE": _COOKIE_SECURE,
    "ACCESS_TOKEN_COOKIE_SAMESITE": "Lax",
    "REFRESH_TOKEN_COOKIE_SAMESITE": "Lax",
    "ACCESS_TOKEN_COOKIE_PATH": "/",
    "REFRESH_TOKEN_COOKIE_PATH": "/api/v1/auth/token/refresh",
}

REST_AUTH = {
    "USE_JWT": True,
    "JWT_AUTH_HTTPONLY": False,
    "SESSION_LOGIN": False,
    "USER_DETAILS_SERIALIZER": (
        "apps.iam.auth.serializers.UserDetailsSerializer"
    ),
}
