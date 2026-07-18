"""Email verification codes for registration and password reset."""

from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailVerificationCode(models.Model):
    """Single-use email verification code (registration / password reset)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_codes",
    )
    code_hash = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "iam_email_verification_code"
        indexes = [
            models.Index(fields=["user", "is_used", "expires_at"]),
        ]

    @staticmethod
    def generate_code() -> str:
        return str(secrets.randbelow(900000) + 100000)

    @staticmethod
    def hash_code(plain_code: str) -> str:
        return hashlib.sha256(plain_code.encode()).hexdigest()

    @property
    def is_valid(self) -> bool:
        return timezone.now() < self.expires_at and not self.is_used
