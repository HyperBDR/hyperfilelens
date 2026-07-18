"""
Org-scoped DRF permissions (IAM domain).

This is business-domain aware (depends on Organization/Membership models) and
therefore lives under apps/iam, not core/.
"""

from __future__ import annotations

from types import SimpleNamespace

from rest_framework import permissions
from rest_framework.request import Request

from apps.iam.models import Membership, Organization
from apps.platform_ops.constants import SUPPORT_SESSION_KEY


def resolve_org_key(request: Request) -> str:
    return str(
        request.headers.get("X-Org-Key", "")
        or request.query_params.get("org", "")
        or ""
    ).strip()


def get_membership(request: Request) -> Membership | None:
    user = request.user
    if not user or not user.is_authenticated:
        return None
    org_key = resolve_org_key(request)
    if not org_key:
        return None
    org = Organization.objects.filter(key=org_key, is_active=True).first()
    if org is None:
        return None
    membership = (
        Membership.objects.select_related("organization", "user")
        .filter(user=user, organization=org, is_active=True)
        .first()
    )
    if membership is not None:
        return membership
    if user.is_staff and request.session.get(SUPPORT_SESSION_KEY) == org_key:
        request.hfl_support_readonly = True
        return SimpleNamespace(
            user=user,
            organization=org,
            role=Membership.Role.AUDITOR,
            is_active=True,
            id=0,
            pk=0,
        )
    return None


class IsOrgMember(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        return get_membership(request) is not None


class _RoleMixin:
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        if getattr(request, "hfl_support_readonly", False) and request.method not in permissions.SAFE_METHODS:
            return False
        membership = get_membership(request)
        if membership is None:
            return False
        if not self.allowed_roles:
            return True
        return membership.role in self.allowed_roles


class IsOrgReader(_RoleMixin, permissions.BasePermission):
    """
    Read-only: auditor + operator + admin + owner
    """

    allowed_roles = (
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.OPERATOR,
        Membership.Role.AUDITOR,
    )

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        if request.method in permissions.SAFE_METHODS:
            return super().has_permission(request, view)
        return False


class IsOrgStaffReader(_RoleMixin, permissions.BasePermission):
    """
    Read-only for operational/config data (excludes auditor).
    """

    allowed_roles = (
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.OPERATOR,
    )

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        if request.method in permissions.SAFE_METHODS:
            return super().has_permission(request, view)
        return False


class IsOrgAdmin(_RoleMixin, permissions.BasePermission):
    """Organization admin: owner + admin (member management, settings)."""

    allowed_roles = (Membership.Role.OWNER, Membership.Role.ADMIN)


class IsOrgWriter(_RoleMixin, permissions.BasePermission):
    """
    Destructive / admin configuration: owner + admin only.
    """

    allowed_roles = (Membership.Role.OWNER, Membership.Role.ADMIN)

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        if request.method in permissions.SAFE_METHODS:
            return get_membership(request) is not None
        return super().has_permission(request, view)


class IsOrgOperator(_RoleMixin, permissions.BasePermission):
    """
    Backup and day-to-day operations: owner + admin + operator.
    """

    allowed_roles = (
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.OPERATOR,
    )

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        if request.method in permissions.SAFE_METHODS:
            return get_membership(request) is not None
        return super().has_permission(request, view)
