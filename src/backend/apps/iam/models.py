"""
IAM domain models: organization/tenant and membership.
"""

import secrets

from django.conf import settings
from django.db import models


class Organization(models.Model):
    """
    Tenant boundary.
    """

    key = models.SlugField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Stable tenant key used in API requests.",
    )
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iam_organization"
        ordering = ["key", "id"]

    def __str__(self):
        return f"{self.name} ({self.key})"


class Membership(models.Model):
    """
    User membership under an organization.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        OPERATOR = "operator", "Operator"
        AUDITOR = "auditor", "Auditor"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OPERATOR,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    preferred_feature = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Optional preferred feature key for landing path within this org.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "iam_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="uniq_iam_user_org",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "role", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(role="owner", is_active=True),
                name="uniq_iam_org_active_owner",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}@{self.organization_id}:{self.role}"


class PersonalApiKey(models.Model):
    """
    Simple personal API key for external integrations.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_api_keys",
    )
    name = models.CharField(max_length=120)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "iam_personal_api_key"
        ordering = ["-created_at", "id"]

    @staticmethod
    def generate_token() -> str:
        return secrets.token_hex(32)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        return super().save(*args, **kwargs)

