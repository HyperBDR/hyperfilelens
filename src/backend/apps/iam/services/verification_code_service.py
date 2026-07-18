"""Verify email codes issued for registration and password reset."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.utils import timezone

from apps.iam.email_verification_models import EmailVerificationCode


def verify_email_verification_code(user: User, code: str) -> tuple[bool, str | None]:
    """
    Verify a 6-digit email verification code.

    Returns:
        (is_valid, error_reason)
    """
    code = str(code or "").strip()
    if not code or len(code) != 6 or not code.isdigit():
        return False, "INVALID_FORMAT"

    code_hash = EmailVerificationCode.hash_code(code)
    try:
        email_code = EmailVerificationCode.objects.get(
            user=user,
            code_hash=code_hash,
            is_used=False,
        )
    except EmailVerificationCode.DoesNotExist:
        return False, "INVALID_CODE"

    if email_code.expires_at < timezone.now():
        return False, "EXPIRED"

    email_code.is_used = True
    email_code.used_at = timezone.now()
    email_code.save(update_fields=["is_used", "used_at"])
    return True, None
