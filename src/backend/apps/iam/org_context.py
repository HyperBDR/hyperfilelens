"""Resolve organization from request headers or query (console / API)."""

from __future__ import annotations

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.iam.models import Organization
from apps.iam.permissions_org import get_membership


def require_org(request: Request) -> Organization:
    membership = get_membership(request)
    if membership is None:
        raise ValidationError(
            {"org": "Organization context required (X-Org-Key or ?org=)."}
        )
    return membership.organization


def require_org_matching_body(
    request: Request,
    body_org: str | None = None,
) -> Organization:
    """
    Resolve the active organization from request context.

    Reject when a write payload includes ``org`` that differs from the active
    tenant (``X-Org-Key`` / ``?org=`` resolved by ``get_membership``).
    """
    org = require_org(request)
    body_key = str(body_org or "").strip()
    if body_key and body_key != org.key:
        raise ValidationError(
            {"org": "Organization key does not match active context."}
        )
    return org
