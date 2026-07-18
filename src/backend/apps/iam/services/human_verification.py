"""Unified human verification: image captcha or Cloudflare Turnstile."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from apps.iam.services.captcha_service import validate_captcha
from apps.iam.services.turnstile_service import get_client_ip, validate_turnstile

CAPTCHA_PROVIDER_IMAGE = "image"
CAPTCHA_PROVIDER_TURNSTILE = "turnstile"


def get_captcha_provider() -> str:
    from apps.platform_ops.services.internal.runtime_settings import captcha_provider as runtime_captcha_provider

    return runtime_captcha_provider()


def is_turnstile_mode() -> bool:
    return get_captcha_provider() == CAPTCHA_PROVIDER_TURNSTILE


def human_verification_field_name() -> str:
    """Frontend error field key for auth captcha inputs."""
    return "code"


def _has_turnstile_token(data: dict) -> bool:
    return bool((data.get("turnstile_token") or "").strip())


def _has_image_captcha(data: dict) -> bool:
    return bool(data.get("id")) and bool(data.get("code"))


def missing_human_verification_fields(data: dict) -> dict[str, list[str]]:
    if is_turnstile_mode():
        if _has_turnstile_token(data) or _has_image_captcha(data):
            return {}
        return {human_verification_field_name(): [_("Required")]}

    fields: dict[str, list[str]] = {}
    if not data.get("id"):
        fields["id"] = [_("Required")]
    if not data.get("code"):
        fields[human_verification_field_name()] = [_("Required")]
    return fields


def credentials_and_human_verification_present(data: dict, credential_fields: list[str]) -> bool:
    if any(not data.get(field) for field in credential_fields):
        return False
    return not missing_human_verification_fields(data)


def verify_human_verification(data: dict, request) -> bool:
    if is_turnstile_mode():
        token = (data.get("turnstile_token") or "").strip()
        if token:
            return validate_turnstile(token, get_client_ip(request))
        captcha_id = data.get("id")
        captcha_code = data.get("code")
        if captcha_id and captcha_code:
            return validate_captcha(captcha_id, captcha_code)
        return False

    captcha_id = data.get("id")
    captcha_code = data.get("code")
    if not captcha_id or not captcha_code:
        return False
    return validate_captcha(captcha_id, captcha_code)


def invalid_human_verification_fields() -> dict[str, list[str]]:
    message = _("Invalid or expired captcha")
    return {human_verification_field_name(): [message]}
