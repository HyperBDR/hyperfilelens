"""
Token blacklist and refresh token rotation service.
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# Token blacklist key prefix
BLACKLIST_PREFIX = "token_blacklist:"
# Refresh token family key prefix
REFRESH_FAMILY_PREFIX = "refresh_family:"
# Refresh token last-used key prefix
REFRESH_LASTUSED_PREFIX = "refresh_lastused:"

# Token lifetimes
ACCESS_TOKEN_LIFETIME = timedelta(hours=1)
REFRESH_TOKEN_LIFETIME = timedelta(hours=24)  # 24 hours as per requirement
ROTATION_TOKEN_LIFETIME = timedelta(days=7)  # New refresh token after rotation


def _lifetime_seconds(setting_name: str, fallback: timedelta) -> int:
    value = getattr(settings, "SIMPLE_JWT", {}).get(setting_name, fallback)
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return int(value)


def get_access_token_lifetime_seconds() -> int:
    return _lifetime_seconds("ACCESS_TOKEN_LIFETIME", ACCESS_TOKEN_LIFETIME)


def get_refresh_token_lifetime_seconds() -> int:
    return _lifetime_seconds("REFRESH_TOKEN_LIFETIME", REFRESH_TOKEN_LIFETIME)


class TokenError:
    """Token-related error codes."""
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    REFRESH_EXPIRED = "REFRESH_EXPIRED"
    TOKEN_BLACKLISTED = "TOKEN_BLACKLISTED"
    OTHER_DEVICE_LOGIN = "OTHER_DEVICE_LOGIN"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    TOKEN_REUSED = "TOKEN_REUSED"
    INVALID_TOKEN = "INVALID_TOKEN"


def _get_blacklist_key(jti: str) -> str:
    return f"{BLACKLIST_PREFIX}{jti}"


def _get_refresh_family_key(user_id: int, family_id: str) -> str:
    return f"{REFRESH_FAMILY_PREFIX}{user_id}:{family_id}"


def _get_refresh_lastused_key(user_id: int) -> str:
    return f"{REFRESH_LASTUSED_PREFIX}{user_id}"


def get_user_token_version(user_id: int) -> int:
    """Get the current token version for a user."""
    version_key = f"user_token_version:{user_id}"
    return cache.get(version_key, 0)


def get_user_token_invalid_reason(user_id: int) -> str:
    """Get the reason the user's previous token version was invalidated."""
    reason_key = f"user_token_invalid_reason:{user_id}"
    return cache.get(reason_key, "")


def get_token_family_version(user_id: int, family_id: str) -> int:
    """Get the token version stored in a specific family."""
    family_key = _get_refresh_family_key(user_id, family_id)
    return cache.get(family_key + ":version", 0)


def is_token_version_valid(user_id: int, token_version: int) -> bool:
    """Check if a token version is still valid (not invalidated by a newer login)."""
    current_version = get_user_token_version(user_id)
    is_valid = token_version == current_version
    logger.info(f"[TOKEN] is_token_version_valid: user_id={user_id}, token_version={token_version}, current_version={current_version}, is_valid={is_valid}")
    return is_valid


def blacklist_token(jti: str, expires_at: Optional[datetime] = None) -> None:
    """
    Add a token (by its jti claim) to the blacklist.
    If expires_at is not provided, blacklist for the default access token lifetime.
    """
    key = _get_blacklist_key(jti)
    if expires_at:
        # Calculate remaining TTL
        remaining = expires_at - timezone.now()
        if remaining.total_seconds() > 0:
            cache.set(key, True, timeout=int(remaining.total_seconds()))
    else:
        cache.set(key, True, timeout=get_access_token_lifetime_seconds())


def is_token_blacklisted(jti: str) -> bool:
    """Check if a token is blacklisted."""
    return cache.get(_get_blacklist_key(jti), False)


def blacklist_all_user_tokens(user_id: int, reason: str) -> None:
    """
    Blacklist all existing refresh tokens for a user.
    Used when password changes or other security events occur.
    """
    # Delete all family keys for this user
    # We store family_id as a unique identifier for each login session
    # When security event occurs, we increment a version number stored separately
    version_key = f"user_token_version:{user_id}"
    reason_key = f"user_token_invalid_reason:{user_id}"
    current_version = cache.get(version_key, 0)
    cache.set(version_key, current_version + 1, timeout=None)
    cache.set(reason_key, reason, timeout=None)
    logger.info(f"[TOKEN] blacklist_all_user_tokens: user_id={user_id}, old_version={current_version}, new_version={current_version + 1}, reason={reason}")


def check_refresh_token_rotation(user_id: int, family_id: str, token_jti: str) -> tuple[bool, Optional[str]]:
    """
    Check and validate refresh token rotation.

    Returns:
        (is_valid, error_code)
        If valid: (True, None)
        If invalid: (False, error_code)

    Rotation logic:
    - Each login session has a unique family_id
    - Each refresh token has a unique jti
    - When a refresh token is used, we store its jti against the family
    - If the same jti is used again, it's a reuse attack
    """
    family_key = _get_refresh_family_key(user_id, family_id)
    version_key = f"user_token_version:{user_id}"

    # Check if token version is still valid
    stored_version = cache.get(family_key + ":version", 0)
    current_version = cache.get(version_key, 0)
    if stored_version != current_version:
        if get_user_token_invalid_reason(user_id) == "password_changed":
            return False, TokenError.PASSWORD_CHANGED
        return False, TokenError.OTHER_DEVICE_LOGIN

    # Store the jti of the refresh token after it has been exchanged.
    # If this jti appears again, an already-rotated refresh token was reused.
    used_jtis_key = family_key + ":used_jtis"
    used_jtis = cache.get(used_jtis_key, set())

    if token_jti in used_jtis:
        # REUSE ATTACK! Invalidate the entire family
        cache.set(family_key + ":version", current_version + 1, timeout=None)
        logger.warning(f"Refresh token reuse detected for user {user_id}, family {family_id}")
        return False, TokenError.TOKEN_REUSED

    # Mark this jti as used
    used_jtis.add(token_jti)
    # Keep the set of used jtis for the lifetime of the family
    cache.set(used_jtis_key, used_jtis, timeout=int(ROTATION_TOKEN_LIFETIME.total_seconds()))

    return True, None


def store_refresh_token_family(user_id: int, family_id: str, refresh_jti: str) -> int:
    """Store a new refresh token family when user logs in. Returns the token version."""
    family_key = _get_refresh_family_key(user_id, family_id)
    version_key = f"user_token_version:{user_id}"

    current_version = cache.get(version_key, 0)
    cache.set(family_key + ":version", current_version, timeout=get_refresh_token_lifetime_seconds())
    cache.set(family_key + ":used_jtis", set(), timeout=int(ROTATION_TOKEN_LIFETIME.total_seconds()))
    cache.set(_get_refresh_lastused_key(user_id), family_id, timeout=get_refresh_token_lifetime_seconds())
    return current_version


def extend_refresh_token_family(user_id: int, family_id: str, token_version: int) -> None:
    """Extend family metadata when a refresh token is rotated successfully."""
    family_key = _get_refresh_family_key(user_id, family_id)
    cache.set(family_key + ":version", token_version, timeout=get_refresh_token_lifetime_seconds())
    cache.set(_get_refresh_lastused_key(user_id), family_id, timeout=get_refresh_token_lifetime_seconds())


def generate_token_family_id() -> str:
    """Generate a unique token family ID for a login session."""
    return secrets.token_hex(16)


def get_token_error_message(error_code: str) -> str:
    """Get human-readable message for token error codes."""
    messages = {
        TokenError.TOKEN_EXPIRED: _("Token has expired, please refresh"),
        TokenError.REFRESH_EXPIRED: _("Login session expired, please login again"),
        TokenError.TOKEN_BLACKLISTED: _("Token has been invalidated"),
        TokenError.OTHER_DEVICE_LOGIN: _("Your account was logged in from another device"),
        TokenError.PASSWORD_CHANGED: _("Your password has been changed"),
        TokenError.ACCOUNT_DISABLED: _("Your account has been disabled"),
        TokenError.TOKEN_REUSED: _("Suspicious login activity detected"),
        TokenError.INVALID_TOKEN: _("Invalid token"),
    }
    return messages.get(error_code, _("Authentication failed"))
