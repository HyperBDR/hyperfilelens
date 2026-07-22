"""Read/write platform runtime settings with .env / Django settings fallback."""

from __future__ import annotations

import json
import os
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser

from apps.platform_ops.models.platform_runtime_setting import PlatformRuntimeSetting
from apps.storage.crypto import decrypt_text, encrypt_text

KEY_EMAIL_BACKEND = "email.backend"
KEY_EMAIL_HOST = "email.host"
KEY_EMAIL_PORT = "email.port"
KEY_EMAIL_USE_TLS = "email.use_tls"
KEY_EMAIL_USE_SSL = "email.use_ssl"
KEY_EMAIL_HOST_USER = "email.host_user"
KEY_EMAIL_FROM = "email.from_email"

KEY_IDENTITY_EMAIL_SIGNUP = "identity.email_signup_enabled"
KEY_IDENTITY_PLATFORM_OPS = "identity.platform_ops_enabled"
KEY_IDENTITY_OPS_CIDRS = "identity.platform_ops_allowed_cidrs"
KEY_IDENTITY_TURNSTILE_SITE = "identity.turnstile_site_key"
KEY_IDENTITY_GOOGLE_CLIENT_ID = "identity.google_client_id"
KEY_IDENTITY_GOOGLE_OAUTH = "identity.google_oauth_enabled"

KEY_AI_OPENAI_BASE = "ai.openai_api_base"
KEY_AI_AZURE_BASE = "ai.azure_openai_api_base"
KEY_AI_LANGFUSE_BASE = "ai.langfuse_base_url"
KEY_AI_LANGFUSE_ENABLED = "ai.langfuse_enabled"

SECRET_KEYS = frozenset(
    {
        "email.host_password",
        "identity.turnstile_secret_key",
        "identity.google_client_secret",
        "ai.openai_api_key",
        "ai.azure_openai_api_key",
        "ai.gemini_api_key",
        "ai.langfuse_public_key",
        "ai.langfuse_secret_key",
    }
)

SECRET_KEY_EMAIL_PASSWORD = "email.host_password"
SECRET_KEY_TURNSTILE = "identity.turnstile_secret_key"
SECRET_KEY_GOOGLE = "identity.google_client_secret"
SECRET_KEY_OPENAI = "ai.openai_api_key"
SECRET_KEY_AZURE = "ai.azure_openai_api_key"
SECRET_KEY_GEMINI = "ai.gemini_api_key"
SECRET_KEY_LANGFUSE_PUBLIC = "ai.langfuse_public_key"
SECRET_KEY_LANGFUSE_SECRET = "ai.langfuse_secret_key"

_CACHE: dict[str, PlatformRuntimeSetting] | None = None

SMTP_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
CONSOLE_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DUMMY_EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
IN_MEMORY_EMAIL_BACKENDS = frozenset(
    {
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    }
)
EMAIL_RUNTIME_KEYS = (
    KEY_EMAIL_BACKEND,
    KEY_EMAIL_HOST,
    KEY_EMAIL_PORT,
    KEY_EMAIL_USE_TLS,
    KEY_EMAIL_USE_SSL,
    KEY_EMAIL_HOST_USER,
    SECRET_KEY_EMAIL_PASSWORD,
    KEY_EMAIL_FROM,
)


def invalidate_runtime_settings_cache() -> None:
    global _CACHE
    _CACHE = None


def _rows_by_key() -> dict[str, PlatformRuntimeSetting]:
    global _CACHE
    if _CACHE is None:
        _CACHE = {row.key: row for row in PlatformRuntimeSetting.objects.all()}
    return _CACHE


def _row(key: str) -> PlatformRuntimeSetting | None:
    return _rows_by_key().get(key)


def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _settings_str(attr: str, default: str = "") -> str:
    return str(getattr(settings, attr, default) or "").strip()


def _parse_bool(raw: str, *, default: bool) -> bool:
    if raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _runtime_raw(key: str) -> tuple[str, bool]:
    """Return (value, is_runtime). Secret values only when needed internally."""
    row = _row(key)
    if row is None:
        return "", False
    if row.secret_ciphertext:
        return decrypt_text(row.secret_ciphertext), True
    return (row.value_text or "").strip(), True


def get_source(key: str) -> str:
    if _row(key) is not None:
        row = _row(key)
        if row and (row.secret_ciphertext or (row.value_text or "").strip()):
            return "runtime"
    return "env"


def get_str(key: str, *, env_name: str = "", settings_attr: str = "", default: str = "") -> str:
    raw, from_runtime = _runtime_raw(key)
    if from_runtime and raw:
        return raw
    if env_name:
        val = _env_str(env_name)
        if val:
            return val
    if settings_attr:
        val = _settings_str(settings_attr)
        if val:
            return val
    return default


def get_secret(key: str, *, env_name: str = "", settings_attr: str = "", default: str = "") -> str:
    raw, from_runtime = _runtime_raw(key)
    if from_runtime and raw:
        return raw
    if env_name:
        val = _env_str(env_name)
        if val:
            return val
    if settings_attr:
        return _settings_str(settings_attr, default)
    return default


def get_bool(
    key: str,
    *,
    env_name: str = "",
    settings_attr: str = "",
    default: bool = False,
) -> bool:
    raw, from_runtime = _runtime_raw(key)
    if from_runtime and raw != "":
        return _parse_bool(raw, default=default)
    if env_name:
        env_val = _env_str(env_name)
        if env_val:
            return _parse_bool(env_val, default=default)
    if settings_attr:
        return bool(getattr(settings, settings_attr, default))
    return default


def get_int(key: str, *, env_name: str = "", settings_attr: str = "", default: int = 0) -> int:
    raw, from_runtime = _runtime_raw(key)
    if from_runtime and raw != "":
        try:
            return int(raw)
        except ValueError:
            return default
    if env_name:
        env_val = _env_str(env_name)
        if env_val:
            try:
                return int(env_val)
            except ValueError:
                pass
    if settings_attr:
        try:
            return int(getattr(settings, settings_attr, default))
        except (TypeError, ValueError):
            return default
    return default


def get_str_list(key: str, *, settings_attr: str = "") -> list[str]:
    raw, from_runtime = _runtime_raw(key)
    if from_runtime and raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            return [part.strip() for part in raw.split(",") if part.strip()]
    if settings_attr:
        val = getattr(settings, settings_attr, None)
        if isinstance(val, (list, tuple)):
            return [str(x).strip() for x in val if str(x).strip()]
    return []


def secret_configured(key: str, *, env_name: str = "", settings_attr: str = "") -> bool:
    row = _row(key)
    if row and row.secret_ciphertext:
        return True
    if env_name and _env_str(env_name):
        return True
    if settings_attr and _settings_str(settings_attr):
        return True
    return False


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def set_value(
    *,
    key: str,
    value: str | None = None,
    secret: str | None = None,
    user: AbstractBaseUser | None = None,
    clear: bool = False,
) -> None:
    if clear:
        PlatformRuntimeSetting.objects.filter(key=key).delete()
        invalidate_runtime_settings_cache()
        return

    row, _created = PlatformRuntimeSetting.objects.get_or_create(key=key)
    update_fields = ["updated_at"]
    if user is not None:
        row.updated_by = user
        update_fields.append("updated_by")

    if secret is not None:
        secret = secret.strip()
        if secret == "":
            pass
        else:
            row.secret_ciphertext = encrypt_text(secret)
            row.value_text = ""
            update_fields.extend(["secret_ciphertext", "value_text"])
    elif value is not None:
        row.value_text = value.strip() if isinstance(value, str) else str(value)
        row.secret_ciphertext = ""
        update_fields.extend(["value_text", "secret_ciphertext"])

    row.save(update_fields=update_fields)
    invalidate_runtime_settings_cache()


def set_bool(key: str, value: bool, *, user: AbstractBaseUser | None = None) -> None:
    set_value(key=key, value="true" if value else "false", user=user)


def set_str_list(key: str, values: list[str], *, user: AbstractBaseUser | None = None) -> None:
    set_value(key=key, value=json.dumps(values), user=user)


# --- Effective getters used by overlay consumers ---


def email_signup_enabled() -> bool:
    """Return whether anonymous email/password account creation is allowed."""
    return get_bool(
        KEY_IDENTITY_EMAIL_SIGNUP,
        env_name="HFL_EMAIL_SIGNUP_ENABLED",
        settings_attr="HFL_EMAIL_SIGNUP_ENABLED",
        default=False,
    )


def platform_ops_enabled() -> bool:
    return get_bool(
        KEY_IDENTITY_PLATFORM_OPS,
        env_name="HFL_PLATFORM_OPS_ENABLED",
        settings_attr="HFL_PLATFORM_OPS_ENABLED",
        default=True,
    )


def platform_ops_allowed_cidrs() -> list[str]:
    return get_str_list(KEY_IDENTITY_OPS_CIDRS, settings_attr="HFL_PLATFORM_OPS_ALLOWED_CIDRS")


def turnstile_enabled() -> bool:
    """Return the deployment-controlled Turnstile feature flag."""
    return bool(getattr(settings, "TURNSTILE_ENABLED", False))


def turnstile_site_key() -> str:
    return get_str(
        KEY_IDENTITY_TURNSTILE_SITE,
        env_name="TURNSTILE_SITE_KEY",
        settings_attr="TURNSTILE_SITE_KEY",
    )


def turnstile_secret_key() -> str:
    return get_secret(
        SECRET_KEY_TURNSTILE,
        env_name="TURNSTILE_SECRET_KEY",
        settings_attr="TURNSTILE_SECRET_KEY",
    )


def google_client_id() -> str:
    return get_str(
        KEY_IDENTITY_GOOGLE_CLIENT_ID,
        env_name="GOOGLE_CLIENT_ID",
        settings_attr="GOOGLE_CLIENT_ID",
    )


def google_client_secret() -> str:
    return get_secret(
        SECRET_KEY_GOOGLE,
        env_name="GOOGLE_CLIENT_SECRET",
        settings_attr="GOOGLE_CLIENT_SECRET",
    )


def google_oauth_enabled() -> bool:
    """Return whether Google OAuth is explicitly enabled and configured."""
    policy_enabled = get_bool(
        KEY_IDENTITY_GOOGLE_OAUTH,
        env_name="HFL_GOOGLE_OAUTH_ENABLED",
        settings_attr="HFL_GOOGLE_OAUTH_ENABLED",
        default=False,
    )
    return bool(policy_enabled and google_client_id() and google_client_secret())


def _settings_email_connection_kwargs() -> dict[str, Any]:
    """Return process environment-backed Django mail settings without DB overlays."""
    return {
        "backend": _settings_str("EMAIL_BACKEND", CONSOLE_EMAIL_BACKEND),
        "host": _settings_str("EMAIL_HOST"),
        "port": int(getattr(settings, "EMAIL_PORT", 587) or 0),
        "username": _settings_str("EMAIL_HOST_USER"),
        "password": _settings_str("EMAIL_HOST_PASSWORD"),
        "use_tls": bool(getattr(settings, "EMAIL_USE_TLS", False)),
        "use_ssl": bool(getattr(settings, "EMAIL_USE_SSL", False)),
        "from_email": _settings_str(
            "DEFAULT_FROM_EMAIL",
            "HyperFileLens <noreply@hyperfilelens.local>",
        ),
    }


def _runtime_email_connection_kwargs() -> dict[str, Any]:
    return {
        "backend": get_str(
            KEY_EMAIL_BACKEND,
            settings_attr="EMAIL_BACKEND",
            default=CONSOLE_EMAIL_BACKEND,
        ),
        "host": get_str(KEY_EMAIL_HOST, settings_attr="EMAIL_HOST"),
        "port": get_int(
            KEY_EMAIL_PORT,
            settings_attr="EMAIL_PORT",
            default=587,
        ),
        "username": get_str(
            KEY_EMAIL_HOST_USER,
            settings_attr="EMAIL_HOST_USER",
        ),
        "password": get_secret(
            SECRET_KEY_EMAIL_PASSWORD,
            settings_attr="EMAIL_HOST_PASSWORD",
        ),
        "use_tls": get_bool(
            KEY_EMAIL_USE_TLS,
            settings_attr="EMAIL_USE_TLS",
            default=False,
        ),
        "use_ssl": get_bool(
            KEY_EMAIL_USE_SSL,
            settings_attr="EMAIL_USE_SSL",
            default=False,
        ),
        "from_email": get_str(
            KEY_EMAIL_FROM,
            settings_attr="DEFAULT_FROM_EMAIL",
            default="HyperFileLens <noreply@hyperfilelens.local>",
        ),
    }


def validate_email_connection_config(config: dict[str, Any]) -> str:
    """Return a stable configuration error, or an empty string when deliverable."""
    backend = str(config.get("backend") or "").strip()
    if backend in IN_MEMORY_EMAIL_BACKENDS:
        return ""
    if backend in {"", CONSOLE_EMAIL_BACKEND, DUMMY_EMAIL_BACKEND}:
        return "SMTP email delivery is not configured."
    if backend != SMTP_EMAIL_BACKEND:
        return "Unsupported email backend."

    missing = [
        label
        for label, value in (
            ("host", config.get("host")),
            ("username", config.get("username")),
            ("password", config.get("password")),
            ("from_email", config.get("from_email")),
        )
        if not str(value or "").strip()
    ]
    if missing:
        return f"SMTP configuration is missing: {', '.join(missing)}."
    try:
        port = int(config.get("port") or 0)
    except (TypeError, ValueError):
        return "SMTP port must be an integer between 1 and 65535."
    if port < 1 or port > 65535:
        return "SMTP port must be an integer between 1 and 65535."
    if bool(config.get("use_tls")) and bool(config.get("use_ssl")):
        return "SMTP SSL and STARTTLS cannot both be enabled."
    return ""


def _deployment_email_has_intent(config: dict[str, Any]) -> bool:
    backend = str(config.get("backend") or "").strip()
    return bool(
        backend == SMTP_EMAIL_BACKEND
        or str(config.get("host") or "").strip()
        or str(config.get("username") or "").strip()
        or str(config.get("password") or "").strip()
    )


def email_settings_managed_by_deployment() -> bool:
    """Whether process environment SMTP values own the effective configuration."""
    return _deployment_email_has_intent(_settings_email_connection_kwargs())


def _runtime_email_configured() -> bool:
    return any(_row(key) is not None for key in EMAIL_RUNTIME_KEYS)


def email_connection_kwargs() -> dict[str, Any]:
    environment = _settings_email_connection_kwargs()
    managed = _deployment_email_has_intent(environment)
    config = environment if managed else _runtime_email_connection_kwargs()
    source = "deployment" if managed else ("runtime" if _runtime_email_configured() else "default")
    return {
        **config,
        "source": source,
        "managed_by_deployment": managed,
        "configuration_error": validate_email_connection_config(config),
    }


def email_delivery_configured() -> bool:
    return not bool(email_connection_kwargs()["configuration_error"])


def openai_api_key() -> str | None:
    val = get_secret(SECRET_KEY_OPENAI, env_name="OPENAI_API_KEY")
    return val or None


def openai_api_base() -> str:
    return get_str(
        KEY_AI_OPENAI_BASE,
        env_name="OPENAI_API_BASE",
        default="https://api.openai.com/v1/",
    )


def azure_openai_api_key() -> str | None:
    val = get_secret(SECRET_KEY_AZURE, env_name="AZURE_OPENAI_API_KEY")
    return val or None


def azure_openai_api_base() -> str | None:
    val = get_str(KEY_AI_AZURE_BASE, env_name="AZURE_OPENAI_API_BASE")
    return val or None


def gemini_api_key() -> str | None:
    val = get_secret(SECRET_KEY_GEMINI, env_name="GEMINI_API_KEY") or get_secret(
        SECRET_KEY_GEMINI,
        env_name="GOOGLE_API_KEY",
    )
    return val or None


def langfuse_public_key() -> str:
    return get_secret(SECRET_KEY_LANGFUSE_PUBLIC, env_name="LANGFUSE_PUBLIC_KEY")


def langfuse_secret_key() -> str:
    return get_secret(SECRET_KEY_LANGFUSE_SECRET, env_name="LANGFUSE_SECRET_KEY")


def langfuse_base_url() -> str:
    return get_str(KEY_AI_LANGFUSE_BASE, env_name="LANGFUSE_BASE_URL", default="http://localhost:3000")


def langfuse_enabled() -> bool:
    if get_bool(KEY_AI_LANGFUSE_ENABLED, env_name="LANGFUSE_ENABLED", default=False):
        return True
    return _parse_bool(_env_str("LANGFUSE_ENABLED"), default=False)


def sync_google_social_app() -> None:
    """Keep django-allauth SocialApp in sync with runtime Google OAuth credentials."""
    client_id = google_client_id()
    secret = google_client_secret()
    if not client_id or not secret:
        return
    try:
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site

        site = Site.objects.get_current()
        app, _created = SocialApp.objects.update_or_create(
            provider="google",
            defaults={
                "name": "Google",
                "client_id": client_id,
                "secret": secret,
            },
        )
        app.sites.add(site)
    except Exception:
        pass
