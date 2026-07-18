"""HFL-side assistant visibility enforcement."""

from __future__ import annotations

import uuid as uuid_lib
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from apps.iam.models import Membership, Organization
from apps.lens_bridge.models import LensAssistantLink, LensKnowledgeSource


def can_manage_all_assistants(membership: Membership | None) -> bool:
    if membership is None:
        return False
    return membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)


def parse_visibility_scope(raw: Any, *, default: str = LensAssistantLink.VisibilityScope.USER) -> str:
    scope = str(raw or default).strip().lower()
    valid = {
        LensAssistantLink.VisibilityScope.USER,
        LensAssistantLink.VisibilityScope.ORGANIZATION,
    }
    if scope not in valid:
        raise ValueError(f"Invalid visibility scope: {scope!r}")
    return scope


def assistant_visible_to(
    *,
    user: AbstractBaseUser,
    link: LensAssistantLink,
    manage: bool = False,
    membership: Membership | None = None,
) -> bool:
    if manage and can_manage_all_assistants(membership):
        return True
    if link.visibility_scope == LensAssistantLink.VisibilityScope.ORGANIZATION:
        return True
    return link.owner_user_id == user.id


def links_for_org(org: Organization) -> dict[str, LensAssistantLink]:
    rows = LensAssistantLink.objects.filter(organization=org).select_related(
        "knowledge_source",
        "knowledge_source__gateway",
        "owner_user",
        "created_by",
    )
    return {str(row.sl_assistant_uuid): row for row in rows}


def get_assistant_link(org: Organization, assistant_uuid: uuid_lib.UUID) -> LensAssistantLink | None:
    return (
        LensAssistantLink.objects.filter(
            organization=org,
            sl_assistant_uuid=assistant_uuid,
        )
        .select_related("knowledge_source", "knowledge_source__gateway", "owner_user", "created_by")
        .first()
    )


def ensure_assistant_link(
    *,
    org: Organization,
    sl_assistant_uuid: uuid_lib.UUID,
    knowledge_source: LensKnowledgeSource | None = None,
    visibility_scope: str | None = None,
    owner_user: AbstractBaseUser | None = None,
    created_by: AbstractBaseUser | None = None,
) -> LensAssistantLink:
    scope = visibility_scope or LensAssistantLink.VisibilityScope.ORGANIZATION
    ks = knowledge_source
    if ks is None:
        ks = (
            LensKnowledgeSource.objects.filter(
                organization=org,
                sl_assistant_uuid=sl_assistant_uuid,
            )
            .first()
        )
    defaults: dict[str, Any] = {
        "visibility_scope": scope,
        "knowledge_source": ks,
        "created_by": created_by or (ks.created_by if ks else None),
    }
    if scope == LensAssistantLink.VisibilityScope.USER:
        defaults["owner_user"] = owner_user or created_by or (ks.created_by if ks else None)
    else:
        defaults["owner_user"] = None

    existing = LensAssistantLink.all_objects.filter(
        organization=org,
        sl_assistant_uuid=sl_assistant_uuid,
    ).first()
    if existing is not None:
        if existing.is_deleted:
            for key, value in defaults.items():
                setattr(existing, key, value)
            existing.is_deleted = False
            existing.deleted_at = None
            existing.save()
            return existing
        return existing

    return LensAssistantLink.objects.create(
        organization=org,
        sl_assistant_uuid=sl_assistant_uuid,
        **defaults,
    )


def soft_delete_assistant_link(org: Organization, assistant_uuid: uuid_lib.UUID) -> None:
    """Hide an assistant from HFL lists; keeps a tombstone to block auto-relink."""
    link = LensAssistantLink.all_objects.filter(
        organization=org,
        sl_assistant_uuid=assistant_uuid,
    ).first()
    if link is not None:
        if not link.is_deleted:
            link.soft_delete()
        return
    LensAssistantLink.all_objects.create(
        organization=org,
        sl_assistant_uuid=assistant_uuid,
        visibility_scope=LensAssistantLink.VisibilityScope.ORGANIZATION,
        is_deleted=True,
        deleted_at=timezone.now(),
    )


def merge_link_fields(row: dict[str, Any], link: LensAssistantLink | None) -> dict[str, Any]:
    merged = dict(row)
    if link is not None:
        merged["visibility_scope"] = link.visibility_scope
        merged["owner_user_id"] = link.owner_user_id
        merged["knowledge_source_id"] = (
            link.knowledge_source_id
            if link.knowledge_source_id is not None
            else merged.get("knowledge_source_id")
        )
    else:
        merged.setdefault("visibility_scope", LensAssistantLink.VisibilityScope.ORGANIZATION)
    merged["visibility"] = "private"
    return merged
