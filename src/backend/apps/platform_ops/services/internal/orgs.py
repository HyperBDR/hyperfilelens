"""Organization write operations for Platform Ops."""

from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify

from apps.iam.models import Membership, Organization
from apps.platform_ops.services.internal.audit import write_platform_audit_log


@transaction.atomic
def create_platform_organization(
    *,
    request,
    key: str,
    name: str,
    owner_user_id: int,
    is_active: bool = True,
) -> Organization:
    key = slugify(key)[:64] or key.strip().lower()[:64]
    if Organization.objects.filter(key=key).exists():
        raise ValueError("Organization key already exists")
    from django.contrib.auth import get_user_model

    User = get_user_model()
    owner = User.objects.filter(pk=owner_user_id).first()
    if owner is None:
        raise ValueError("Owner user not found")

    org = Organization.objects.create(key=key, name=name.strip(), is_active=is_active)
    Membership.objects.create(
        user=owner,
        organization=org,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    write_platform_audit_log(
        request=request,
        action="org.create",
        target_type="organization",
        target_id=str(org.id),
        org_key=org.key,
        details={"name": org.name, "owner_user_id": owner_user_id},
    )
    return org


@transaction.atomic
def update_platform_organization(org: Organization, *, request, **fields) -> Organization:
    update_fields: list[str] = []
    if "name" in fields and fields["name"] is not None:
        org.name = str(fields["name"]).strip()
        update_fields.append("name")
    if "is_active" in fields and fields["is_active"] is not None:
        org.is_active = bool(fields["is_active"])
        update_fields.append("is_active")
    if update_fields:
        org.save(update_fields=update_fields + ["updated_at"])
        write_platform_audit_log(
            request=request,
            action="org.update",
            target_type="organization",
            target_id=str(org.id),
            org_key=org.key,
            details={k: fields[k] for k in fields if fields[k] is not None},
        )
    return org


@transaction.atomic
def delete_platform_organization(*, org: Organization, request) -> None:
    org_key = org.key
    org_id = org.pk
    org_name = org.name
    org.delete()
    write_platform_audit_log(
        request=request,
        action="org.delete",
        target_type="organization",
        target_id=str(org_id),
        org_key=org_key,
        details={"name": org_name},
    )
