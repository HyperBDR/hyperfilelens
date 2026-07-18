"""Platform staff flags: product uses is_staff; is_superuser stays in sync for Django Admin."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


def apply_platform_staff(user: AbstractBaseUser, is_staff: bool) -> None:
    """Set platform staff and mirror is_superuser (Django Admin break-glass)."""
    user.is_staff = is_staff
    user.is_superuser = is_staff


def platform_staff_update_fields(*, include_password: bool = False) -> list[str]:
    fields = ["is_staff", "is_superuser"]
    if include_password:
        fields.append("password")
    return fields
