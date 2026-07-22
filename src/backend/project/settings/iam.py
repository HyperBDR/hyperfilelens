"""
IAM deployment: email transport, OAuth wiring, frontend URLs.

Policy defaults (token expiry, verification code TTL) live in ``apps.iam.conf``
and are read via ``apps.iam.config`` / GlobalConfig.
"""

from urllib.parse import urlparse

from .env import env_bool, env_int, env_str

EMAIL_BACKEND = env_str(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env_str("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS")
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL")
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "HyperFileLens <noreply@hyperfilelens.local>")

FRONTEND_URL = env_str("FRONTEND_URL", "http://localhost:3000")
LOGIN_REDIRECT_URL = "/accounts/oauth/callback/"

# OAuth state is stored in the session; HTTPS frontends need Secure session cookies so
# the cookie survives the cross-site redirect back from Google.
if FRONTEND_URL.startswith("https://") and not env_str("SESSION_COOKIE_SECURE"):
    SESSION_COOKIE_SECURE = True
if FRONTEND_URL.startswith("https://") and not env_str("CSRF_COOKIE_SECURE"):
    CSRF_COOKIE_SECURE = True

GOOGLE_CLIENT_ID = env_str("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env_str("GOOGLE_CLIENT_SECRET")
HFL_GOOGLE_OAUTH_ENABLED = env_bool("HFL_GOOGLE_OAUTH_ENABLED", default=False)
GOOGLE_OAUTH_ENABLED = bool(
    HFL_GOOGLE_OAUTH_ENABLED and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
)

SOCIALACCOUNT_ADAPTER = "apps.iam.auth.adapters.CustomSocialAccountAdapter"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {
            "access_type": "online",
            # Enterprise SaaS: always show Google account picker (work vs personal).
            "prompt": "select_account",
        },
        "APP": {
            "client_id": GOOGLE_CLIENT_ID,
            "secret": GOOGLE_CLIENT_SECRET,
            "key": "",
        },
    },
}

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = False
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# allauth defaults to 5s; outbound HTTP_PROXY to Google is often slower.
_proxy_configured = bool(env_str("HTTP_PROXY") or env_str("HTTPS_PROXY"))
_default_oauth_timeout = 30 if _proxy_configured else 5
SOCIALACCOUNT_REQUESTS_TIMEOUT = env_int(
    "SOCIALACCOUNT_REQUESTS_TIMEOUT",
    _default_oauth_timeout,
)

ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_METHODS = ["email", "username"]


def _frontend_http_protocol(frontend_url: str) -> str:
    scheme = urlparse(frontend_url).scheme
    return scheme if scheme in ("http", "https") else "http"


# nginx TLS termination: allauth absolute URLs use the same scheme as FRONTEND_URL.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = _frontend_http_protocol(FRONTEND_URL)

SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

HEADLESS_ONLY = False


def _headless_frontend_urls(frontend_url: str) -> dict[str, str]:
    base = frontend_url.rstrip("/")
    return {
        "socialaccount_login_error": f"{base}/auth/oauth/error",
        "account_confirm_email": f"{base}/account/verify-email/{{key}}",
        "account_reset_password": f"{base}/account/password/reset",
        "account_reset_password_from_key": (
            f"{base}/account/password/reset/key/{{key}}"
        ),
    }


HEADLESS_FRONTEND_URLS = _headless_frontend_urls(FRONTEND_URL)

# Turnstile is opt-in. Local and private deployments stay verification-free unless
# the deployment explicitly enables it and supplies both keys.
TURNSTILE_ENABLED = env_bool("TURNSTILE_ENABLED", default=False)
TURNSTILE_SITE_KEY = env_str("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = env_str("TURNSTILE_SECRET_KEY")
