"""Organization-scoped SourceLens LLM config ownership."""

from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth import get_user_model
from rest_framework.exceptions import NotFound, ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import LensOrgLink, LensOrgModelLink
from apps.lens_bridge.services import provisioning, sl_client

User = get_user_model()


def org_model_links(org: Organization):
    return LensOrgModelLink.objects.filter(
        organization=org,
        is_deleted=False,
    ).order_by("created_at", "id")


def org_model_uuids(org: Organization) -> list[uuid.UUID]:
    return list(org_model_links(org).values_list("sl_config_uuid", flat=True))


def default_model_display_name(data: dict[str, Any]) -> str:
    provider = str(data.get("provider") or "provider").strip()
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    model = str(config.get("model") or "—").strip() or "—"
    return f"{provider} · {model}"


def merge_model_display_name(data: dict[str, Any], link: LensOrgModelLink | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return data
    out = dict(data)
    stored = (link.display_name if link else "") or ""
    out["name"] = stored.strip() or default_model_display_name(out)
    out["deployment_managed"] = bool(link and link.management_key)
    return out


def deployment_managed_model_uuid(org: Organization) -> uuid.UUID | None:
    """Return the active deployment-managed model UUID for an organization."""

    return (
        org_model_links(org)
        .exclude(management_key="")
        .values_list("sl_config_uuid", flat=True)
        .first()
    )


def set_model_display_name(link: LensOrgModelLink, name: str | None) -> None:
    if name is None:
        return
    cleaned = str(name).strip()[:160]
    if cleaned == link.display_name:
        return
    link.display_name = cleaned
    link.save(update_fields=["display_name", "updated_at"])


def register_org_model(
    *,
    org: Organization,
    sl_config_uuid: uuid.UUID,
    created_by: User | None = None,
) -> LensOrgModelLink:
    link, created = LensOrgModelLink.objects.get_or_create(
        organization=org,
        sl_config_uuid=sl_config_uuid,
        defaults={"created_by": created_by},
    )
    if not created and link.is_deleted:
        link.is_deleted = False
        link.deleted_at = None
        if created_by is not None:
            link.created_by = created_by
        link.save(update_fields=["is_deleted", "deleted_at", "created_by", "updated_at"])
    ensure_org_default_model(org)
    return link


def require_org_model(org: Organization, config_uuid: uuid.UUID) -> LensOrgModelLink:
    link = org_model_links(org).filter(sl_config_uuid=config_uuid).first()
    if link is None:
        raise NotFound("AI model not found for this organization.")
    return link


def ensure_org_default_model(org: Organization) -> LensOrgLink:
    org_link = provisioning.get_or_create_org_link(org)
    if org_link.default_agent_model_ref:
        if org_model_links(org).filter(sl_config_uuid=org_link.default_agent_model_ref).exists():
            return org_link
        org_link.default_agent_model_ref = None

    first_uuid = org_model_links(org).values_list("sl_config_uuid", flat=True).first()
    if first_uuid:
        org_link.default_agent_model_ref = first_uuid
        org_link.save(update_fields=["default_agent_model_ref", "updated_at"])
    elif org_link.default_agent_model_ref:
        org_link.default_agent_model_ref = None
        org_link.save(update_fields=["default_agent_model_ref", "updated_at"])
    return org_link


def list_org_model_configs(org: Organization) -> list[dict[str, Any]]:
    uuids = org_model_uuids(org)
    if not uuids:
        ensure_org_default_model(org)
        return []

    rows: list[dict[str, Any]] = []
    for config_uuid in uuids:
        try:
            data = sl_client.request_json("GET", f"/api/v1/admin/llm-config/{config_uuid}/")
        except sl_client.LensBridgeError:
            continue
        if isinstance(data, dict):
            link = org_model_links(org).filter(sl_config_uuid=config_uuid).first()
            rows.append(merge_model_display_name(data, link))

    ensure_org_default_model(org)
    return rows


def list_all_llm_configs(*, org: Organization | None = None) -> list[dict[str, Any]]:
    """Full SL admin LLM config list (no org-link filter).

    Optionally merges display_name from HFL links for ``org`` when present.
    """
    from apps.lens_bridge.services.assistants import _unwrap_list

    try:
        raw = sl_client.request_json("GET", "/api/v1/admin/llm-config/")
        rows = _unwrap_list(raw)
    except sl_client.LensBridgeError:
        # Fallback: some SL builds only expose per-uuid GET.
        if org is not None:
            return list_org_model_configs(org)
        return []

    if org is None:
        return [
            merge_model_display_name(row, None) if isinstance(row, dict) else row
            for row in rows
            if isinstance(row, dict)
        ]

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_uuid = row.get("uuid")
        link = None
        if raw_uuid:
            try:
                link = org_model_links(org).filter(sl_config_uuid=uuid.UUID(str(raw_uuid))).first()
            except (TypeError, ValueError):
                link = None
        out.append(merge_model_display_name(row, link))
    return out


def active_llm_configs(*, org: Organization) -> list[dict[str, Any]]:
    """Return active platform models in SourceLens ordering."""
    rows: list[dict[str, Any]] = []
    for row in list_all_llm_configs(org=org):
        status = str(row.get("status") or "").strip().lower()
        if row.get("is_active") is False or status in {"inactive", "disabled"}:
            continue
        if row.get("uuid"):
            rows.append(row)
    return rows


def delete_org_model(org: Organization, config_uuid: uuid.UUID) -> None:
    require_org_model(org, config_uuid)
    sl_client.request_json("DELETE", f"/api/v1/admin/llm-config/{config_uuid}/")
    LensOrgModelLink.objects.filter(
        organization=org,
        sl_config_uuid=config_uuid,
    ).update(is_deleted=True)
    org_link = provisioning.get_or_create_org_link(org)
    if org_link.default_agent_model_ref == config_uuid:
        org_link.default_agent_model_ref = None
        org_link.save(update_fields=["default_agent_model_ref", "updated_at"])
    ensure_org_default_model(org)


def validate_default_model_ref(org: Organization, config_uuid: uuid.UUID | None) -> None:
    if config_uuid is None:
        return
    if not org_model_links(org).filter(sl_config_uuid=config_uuid).exists():
        raise ValidationError(
            {"default_agent_model_ref": "Model does not belong to this organization."}
        )
