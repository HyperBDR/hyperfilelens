"""Platform Ops user write operations."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.iam.models import Membership
from apps.iam.profile_models import Profile
from apps.iam.services.registration_service import (
    provision_registered_user_tenant,
    validate_password_format,
)
from common.platform_staff import apply_platform_staff, platform_staff_update_fields

User = get_user_model()


def _schedule_chat_user_provision(user: User) -> None:
    """Queue SourceLens user provisioning after the database transaction commits."""
    if not user.is_active or user.is_staff:
        return

    user_id = user.pk

    def enqueue() -> None:
        from apps.lens_bridge.services.chat_user_provisioning import (
            enqueue_sl_chat_user_provision,
        )

        enqueue_sl_chat_user_provision(user_id=user_id)

    transaction.on_commit(enqueue)


@transaction.atomic
def create_platform_user(
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    is_active: bool = True,
    is_staff: bool = False,
) -> User:
    email = email.strip().lower()
    is_valid, error_msg = validate_password_format(password)
    if not is_valid:
        raise ValueError(error_msg or "Invalid password")

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        is_active=is_active,
        is_staff=False,
        is_superuser=False,
    )
    apply_platform_staff(user, is_staff)
    user.save(update_fields=platform_staff_update_fields(include_password=False))

    Profile.objects.update_or_create(
        user=user,
        defaults={
            "registration_completed": True,
            "registered_at": timezone.now(),
        },
    )
    if not user.is_staff:
        provision_registered_user_tenant(user)
        _schedule_chat_user_provision(user)
    return user


@transaction.atomic
def update_platform_user(user: User, **fields) -> User:
    update_fields: list[str] = []

    if "email" in fields and fields["email"] is not None:
        email = str(fields["email"]).strip().lower()
        user.email = email
        user.username = email
        update_fields.extend(["email", "username"])

    for attr in ("first_name", "last_name", "is_active"):
        if attr in fields and fields[attr] is not None:
            setattr(user, attr, fields[attr])
            update_fields.append(attr)

    if "is_staff" in fields and fields["is_staff"] is not None:
        apply_platform_staff(user, bool(fields["is_staff"]))
        update_fields.extend(["is_staff", "is_superuser"])

    if update_fields:
        user.save(update_fields=update_fields)
    return user


@transaction.atomic
def reset_platform_user_password(user: User, password: str) -> None:
    is_valid, error_msg = validate_password_format(password)
    if not is_valid:
        raise ValueError(error_msg or "Invalid password")
    user.set_password(password)
    user.save(update_fields=["password"])


@transaction.atomic
def delete_platform_user(*, user: User, actor: User) -> None:
    if actor.pk == user.pk:
        raise ValueError("You cannot delete your own account")
    if Membership.objects.filter(
        user=user,
        role=Membership.Role.OWNER,
        is_active=True,
    ).exists():
        raise ValueError(
            "This user owns an organization. Disable the account or delete the "
            "organization before deleting the user."
        )
    user.delete()
