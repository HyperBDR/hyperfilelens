"""Runtime IAM policy (GlobalConfig with app defaults)."""

from apps.configuration.selectors.interface import get_config
from apps.iam import conf


def get_registration_token_expiry_hours(*, tenant_key: str | None = None) -> int:
    value = get_config(
        conf.CONFIG_KEY_REGISTRATION_TOKEN_EXPIRY_HOURS,
        tenant_key=tenant_key,
        default=conf.DEFAULT_REGISTRATION_TOKEN_EXPIRY_HOURS,
    )
    return int(value)


def get_password_reset_timeout_seconds(*, tenant_key: str | None = None) -> int:
    value = get_config(
        conf.CONFIG_KEY_PASSWORD_RESET_TIMEOUT,
        tenant_key=tenant_key,
        default=conf.DEFAULT_PASSWORD_RESET_TIMEOUT_SECONDS,
    )
    return int(value)


def get_registration_verification_code_minutes(*, tenant_key: str | None = None) -> int:
    value = get_config(
        conf.CONFIG_KEY_REGISTRATION_CODE_MINUTES,
        tenant_key=tenant_key,
        default=conf.DEFAULT_REGISTRATION_VERIFICATION_CODE_MINUTES,
    )
    return int(value)


def get_password_reset_verification_code_minutes(*, tenant_key: str | None = None) -> int:
    value = get_config(
        conf.CONFIG_KEY_PASSWORD_RESET_CODE_MINUTES,
        tenant_key=tenant_key,
        default=conf.DEFAULT_PASSWORD_RESET_VERIFICATION_CODE_MINUTES,
    )
    return int(value)
