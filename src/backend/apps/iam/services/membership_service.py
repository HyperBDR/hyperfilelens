"""Membership write rules (owner uniqueness, role guards)."""

from __future__ import annotations

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apps.iam.models import Membership, Organization


class MembershipPolicyError(ValidationError):
    pass


def active_owner_count(organization: Organization, *, exclude_pk: int | None = None) -> int:
    qs = Membership.objects.filter(
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.count()


def assert_role_assignable(role: str) -> None:
    if role == Membership.Role.OWNER:
        raise MembershipPolicyError(
            {"role": [_("Owner role cannot be assigned via membership API.")]}
        )


def assert_can_deactivate(membership: Membership) -> None:
    if membership.role == Membership.Role.OWNER and membership.is_active:
        raise MembershipPolicyError(
            {"is_active": [_("Cannot deactivate the organization owner.")]}
        )


def assert_can_delete(membership: Membership) -> None:
    if membership.role == Membership.Role.OWNER:
        raise MembershipPolicyError(
            {"detail": [_("Cannot remove the organization owner membership.")]}
        )


@transaction.atomic
def create_org_membership(
    *,
    organization: Organization,
    user,
    role: str,
    is_active: bool = True,
) -> Membership:
    assert_role_assignable(role)
    if Membership.objects.filter(user=user, organization=organization).exists():
        raise MembershipPolicyError(
            {"user": [_("User is already a member of this organization.")]}
        )
    return Membership.objects.create(
        user=user,
        organization=organization,
        role=role,
        is_active=is_active,
    )


@transaction.atomic
def update_org_membership(membership: Membership, **fields) -> Membership:
    if "role" in fields and fields["role"] is not None:
        new_role = fields["role"]
        assert_role_assignable(new_role)
        membership.role = new_role

    if "is_active" in fields and fields["is_active"] is not None:
        new_active = bool(fields["is_active"])
        if membership.is_active and not new_active:
            assert_can_deactivate(membership)
        membership.is_active = new_active

    update_fields = [k for k in ("role", "is_active") if k in fields and fields[k] is not None]
    if update_fields:
        membership.save(update_fields=update_fields)
    return membership
