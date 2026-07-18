"""Enrollment token for node install scripts."""

from __future__ import annotations

import secrets
from typing import Any

from django.conf import settings
from django.db import models

from .base import NodeRole, OrganizationScopedModel


class NodeToken(OrganizationScopedModel):
    """Reusable enrollment token for install scripts (valid until ``expires_at``)."""

    organization = models.ForeignKey(
        "iam.Organization",
        on_delete=models.CASCADE,
        related_name="node_tokens",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=NodeRole.choices)
    note = models.CharField(max_length=200, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(blank=True, null=True, db_index=True)
    used_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="node_tokens_created",
    )
    gateway_scope = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        db_table = "node_tokens"
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(
                fields=["organization", "role", "is_active"],
                name="node_tkn_org_role_act_idx",
            ),
        ]

    @staticmethod
    def generate_token() -> str:
        return secrets.token_hex(32)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)
