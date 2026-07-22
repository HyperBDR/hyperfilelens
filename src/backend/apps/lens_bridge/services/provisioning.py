"""Orchestration helpers for SourceLens Assistant / LensNode provisioning."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import LensGatewayLink, LensKnowledgeSource, LensOrgLink
from apps.lens_bridge.services import ingest_policy, org_models, sl_client
from apps.node.models.base import NodeRole
from apps.node.models.node import Node

logger = logging.getLogger(__name__)

_LENSNODE_DIR_WAIT_SECONDS = 30.0
_LENSNODE_DIR_POLL_SECONDS = 0.5


def get_or_create_org_link(org: Organization) -> LensOrgLink:
    link, _ = LensOrgLink.objects.get_or_create(organization=org)
    return link


def _slugify_assistant(name: str, org: Organization) -> str:
    org_link = get_or_create_org_link(org)
    prefix = org_link.resolved_prefix()
    base = slugify(name) or "source"
    slug = f"{prefix}-{base}"[:160]
    slug = re.sub(r"[^a-z0-9-]", "-", slug.lower())
    return slug.strip("-") or f"{prefix}-source"


def default_model_ref_for_org(org: Organization) -> str | None:
    """Resolve an explicit, deployment-managed, or stable active model."""

    rows = org_models.active_llm_configs(org=org)
    from apps.lens_bridge.services import platform_lens

    platform_org = platform_lens.get_or_create_platform_org()
    org_models.ensure_org_default_model(org)
    org_link = get_or_create_org_link(org)
    if org.pk != platform_org.pk and org_link.default_agent_model_ref:
        tenant_ref = str(org_link.default_agent_model_ref)
        if any(str(row.get("uuid") or "") == tenant_ref for row in rows):
            return tenant_ref

    platform_defaults = get_or_create_org_link(platform_org)
    if platform_defaults.default_agent_model_ref:
        platform_ref = str(platform_defaults.default_agent_model_ref)
        if any(str(row.get("uuid") or "") == platform_ref for row in rows):
            return platform_ref

    managed_uuid = org_models.deployment_managed_model_uuid(platform_org)
    if managed_uuid is not None:
        managed_ref = str(managed_uuid)
        if any(str(row.get("uuid") or "") == managed_ref for row in rows):
            return managed_ref

    for row in rows:
        if not row.get("is_default"):
            continue
        model_uuid = row.get("uuid")
        if model_uuid:
            return str(model_uuid)

    if org_link.default_agent_model_ref:
        legacy_ref = str(org_link.default_agent_model_ref)
        if any(str(row.get("uuid") or "") == legacy_ref for row in rows):
            return legacy_ref

    for row in rows:
        model_uuid = row.get("uuid")
        if model_uuid:
            return str(model_uuid)
    return None


def get_gateway_link(org: Organization, gateway_id: int) -> LensGatewayLink:
    """Resolve gateway link for tenant org, falling back to platform-scoped DG."""
    from apps.lens_bridge.services import platform_lens

    existing = (
        LensGatewayLink.objects.filter(organization=org, gateway_id=gateway_id)
        .select_related("gateway")
        .first()
    )
    if existing is not None:
        return existing

    platform_org = platform_lens.get_or_create_platform_org()
    platform_link = (
        LensGatewayLink.objects.filter(
            organization=platform_org,
            gateway_id=gateway_id,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
        )
        .select_related("gateway")
        .first()
    )
    if platform_link is not None:
        return platform_link

    gateway = require_gateway_node(org, gateway_id)
    link, _ = LensGatewayLink.objects.get_or_create(
        organization=org,
        gateway=gateway,
        defaults={"workspace_root": f"/workspace/org-{org.id}"},
    )
    return link


def require_gateway_node(org: Organization, gateway_id: int) -> Node:
    from apps.lens_bridge.services import platform_lens

    node = Node.objects.filter(
        organization=org,
        id=gateway_id,
        role=NodeRole.GATEWAY,
        is_deleted=False,
    ).first()
    if node is not None:
        return node

    platform_org = platform_lens.get_or_create_platform_org()
    node = Node.objects.filter(
        organization=platform_org,
        id=gateway_id,
        role=NodeRole.GATEWAY,
        is_deleted=False,
    ).first()
    if node is not None:
        return node

    raise ValidationError({"gateway_id": "Data gateway not found."})


def workspace_path_for_ks(org: Organization, gateway_link: LensGatewayLink, ks_id: int) -> str:
    root = gateway_link.resolved_workspace_root()
    return f"{root}/ks-{ks_id}"


def _lensnode_dir_paths(lensnode_data: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for item in lensnode_data.get("available_dirs") or []:
        if isinstance(item, str):
            paths.add(item)
            continue
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if path:
            paths.add(str(path))
        for child in item.get("children") or []:
            if isinstance(child, dict) and child.get("path"):
                paths.add(str(child["path"]))
    return paths


def wait_for_lensnode_dir(
    *,
    lensnode_uuid: uuid.UUID,
    path: str,
    timeout_s: float = _LENSNODE_DIR_WAIT_SECONDS,
) -> None:
    """Wait until a LensNode heartbeat reports the given workspace path."""

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        data = sl_client.request_json("GET", f"/api/lens/admin/lensnodes/{lensnode_uuid}/")
        if path in _lensnode_dir_paths(data):
            return
        time.sleep(_LENSNODE_DIR_POLL_SECONDS)
    raise ValidationError(
        {
            "workspace": (
                f"LensNode did not report workspace path in time: {path}. "
                "Ensure the AI engine is online and retry."
            )
        }
    )


def ensure_ks_workspace_on_gateway(
    *,
    org: Organization,
    gateway: Node,
    gateway_link: LensGatewayLink,
    workspace_path: str,
) -> None:
    """Create the KS workspace directory on the gateway host and wait for LensNode."""

    from apps.node.services.internal.agent_task import run_agent_task_sync

    lensnode_uuid = gateway_link.sl_lensnode_uuid
    if not lensnode_uuid:
        raise ValidationError({"gateway_id": "LensNode is not linked to this gateway."})

    root = gateway_link.resolved_workspace_root()
    outcome = run_agent_task_sync(
        org=org,
        node_id=gateway.id,
        kind="lens.ks.prepare",
        payload={"path": workspace_path, "workspace_root": root},
        correlation_type="lens_knowledge_source",
        wait_timeout_seconds=60,
    )
    if not outcome.ok:
        detail = outcome.task.last_error or "Failed to prepare knowledge source workspace on gateway."
        raise ValidationError({"gateway": detail})

    wait_for_lensnode_dir(lensnode_uuid=lensnode_uuid, path=workspace_path)


def pick_lensnode_task(lensnode_uuid: uuid.UUID) -> str:
    data = sl_client.request_json("GET", f"/api/lens/admin/lensnodes/{lensnode_uuid}/")
    tasks = data.get("tasks") or []
    if not tasks:
        raise ValidationError({"lensnode": "LensNode has no available tasks."})
    first = tasks[0]
    if isinstance(first, dict):
        return str(first.get("name") or first.get("task") or first)
    return str(first)


def indexed_dirs_for_ks(ks: LensKnowledgeSource) -> list[dict[str, str]]:
    from apps.lens_bridge.services.knowledge_source_sync import indexed_dir_paths

    return [{"path": path} for path in indexed_dir_paths(ks)]


def assistant_uuid_for_ks(ks: LensKnowledgeSource) -> uuid.UUID | None:
    """Return the user-linked Assistant for this knowledge source, if any."""
    if ks.sl_assistant_uuid:
        return ks.sl_assistant_uuid
    from apps.lens_bridge.models import LensAssistantLink

    link = (
        LensAssistantLink.objects.filter(
            organization_id=ks.organization_id,
            knowledge_source_id=ks.id,
        )
        .only("sl_assistant_uuid")
        .first()
    )
    if link is not None:
        return link.sl_assistant_uuid
    return None


def sync_linked_assistant_for_ks(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    gateway_link: LensGatewayLink,
) -> uuid.UUID | None:
    """Push KS workspace/index settings to a linked Assistant; never auto-create one."""
    assistant_uuid = assistant_uuid_for_ks(ks)
    if not assistant_uuid:
        return None
    if ks.sl_assistant_uuid != assistant_uuid:
        ks.sl_assistant_uuid = assistant_uuid
        ks.save(update_fields=["sl_assistant_uuid", "updated_at"])
    update_sl_assistant_for_ks(org=org, ks=ks, gateway_link=gateway_link)
    return assistant_uuid


def update_sl_assistant_for_ks(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    gateway_link: LensGatewayLink,
) -> None:
    if not ks.sl_assistant_uuid:
        raise ValidationError({"knowledge_source": "Knowledge source has no linked assistant."})
    lensnode_uuid = gateway_link.sl_lensnode_uuid
    if not lensnode_uuid:
        raise ValidationError({"gateway_id": "LensNode is not linked to this gateway."})

    selected_dirs = indexed_dirs_for_ks(ks)
    policy = ingest_policy.normalize_ingest_policy(ks.ingest_policy_json, org)
    data = sl_client.request_json("GET", f"/api/lens/assistants/{ks.sl_assistant_uuid}/")
    settings = dict(data.get("settings") or {})
    settings["ingestion"] = {
        "conversion": ingest_policy.conversion_payload_for_sl(policy),
    }
    sl_client.request_json(
        "PATCH",
        f"/api/lens/assistants/{ks.sl_assistant_uuid}/",
        json_body={
            "selected_dirs": selected_dirs,
            "settings": settings,
        },
    )


def create_sl_assistant_for_ks(
    *,
    org: Organization,
    ks: LensKnowledgeSource,
    gateway_link: LensGatewayLink,
    model_ref: str | uuid.UUID | None = None,
) -> uuid.UUID:
    lensnode_uuid = gateway_link.sl_lensnode_uuid
    if not lensnode_uuid:
        raise ValidationError({"gateway_id": "LensNode is not linked to this gateway."})

    model_ref = str(model_ref or default_model_ref_for_org(org) or "")
    if not model_ref:
        raise ValidationError(
            {"model": "Set a default AI model in Insights → AI Models before creating knowledge sources."}
        )

    workspace_path = ks.workspace_path_on_lensnode or workspace_path_for_ks(
        org, gateway_link, ks.id
    )
    selected_task = pick_lensnode_task(lensnode_uuid)
    slug = _slugify_assistant(ks.name, org)

    selected_dirs = indexed_dirs_for_ks(ks)
    if not selected_dirs:
        workspace_path = ks.workspace_path_on_lensnode or workspace_path_for_ks(
            org, gateway_link, ks.id
        )
        selected_dirs = [{"path": workspace_path}]

    payload: dict[str, Any] = {
        "name": ks.name,
        "slug": slug,
        "lensnode_uuid": str(lensnode_uuid),
        "selected_task": selected_task,
        "selected_dirs": selected_dirs,
        "agent_model_ref": model_ref,
        "agent_rounds": "balanced",
        "visibility": "private",
        "status": "active",
    }
    policy = ingest_policy.normalize_ingest_policy(ks.ingest_policy_json, org)
    payload["settings"] = {
        "ingestion": {
            "conversion": ingest_policy.conversion_payload_for_sl(policy),
        }
    }
    data = sl_client.request_json("POST", "/api/lens/assistants/", json_body=payload)
    assistant_uuid = data.get("uuid")
    if not assistant_uuid:
        raise sl_client.LensBridgeError("SourceLens assistant create returned no uuid.")
    assistant_uuid_obj = uuid.UUID(str(assistant_uuid))
    from apps.lens_bridge.services import assistant_access

    assistant_access.ensure_assistant_link(
        org=org,
        sl_assistant_uuid=assistant_uuid_obj,
        knowledge_source=ks,
        created_by=ks.created_by,
    )
    return assistant_uuid_obj


def sync_assistant_agent_model(
    *,
    ks: LensKnowledgeSource,
    model_ref: uuid.UUID,
    assistant_uuid: uuid.UUID | None = None,
) -> None:
    """Push agent model selection to the linked SourceLens Assistant."""
    target = assistant_uuid or assistant_uuid_for_ks(ks)
    if not target:
        raise ValidationError({"knowledge_source": "Knowledge source has no linked assistant."})
    if ks.sl_assistant_uuid != target:
        ks.sl_assistant_uuid = target
        ks.save(update_fields=["sl_assistant_uuid", "updated_at"])
    sl_client.request_json(
        "PATCH",
        f"/api/lens/assistants/{target}/",
        json_body={"agent_model_ref": str(model_ref)},
    )


def sync_assistant_ingest_settings(*, org: Organization, ks: LensKnowledgeSource) -> None:
    """Push ingest conversion policy to the linked SourceLens Assistant."""
    if not ks.sl_assistant_uuid:
        return
    data = sl_client.request_json("GET", f"/api/lens/assistants/{ks.sl_assistant_uuid}/")
    settings = dict(data.get("settings") or {})
    policy = ingest_policy.normalize_ingest_policy(ks.ingest_policy_json, org)
    settings["ingestion"] = {
        "conversion": ingest_policy.conversion_payload_for_sl(policy),
    }
    sl_client.request_json(
        "PATCH",
        f"/api/lens/assistants/{ks.sl_assistant_uuid}/",
        json_body={"settings": settings},
    )
    summary = ingest_policy.ingest_summary(policy)
    if ks.status_detail != summary:
        ks.status_detail = summary
        ks.save(update_fields=["status_detail", "updated_at"])


def refresh_ks_status_from_sl(ks: LensKnowledgeSource) -> LensKnowledgeSource:
    if not ks.sl_assistant_uuid:
        return ks
    try:
        data = sl_client.request_json("GET", f"/api/lens/assistants/{ks.sl_assistant_uuid}/")
    except sl_client.LensBridgeError as exc:
        ks.status = LensKnowledgeSource.Status.ERROR
        ks.status_detail = str(exc.detail)
        ks.save(update_fields=["status", "status_detail", "updated_at"])
        return ks

    if data.get("status") == "disabled":
        ks.status = LensKnowledgeSource.Status.PAUSED
    else:
        model_check = (data.get("settings") or {}).get("_model_check") or {}
        agent_check = (model_check.get("agent_model_ref") or {}).get("status")
        if agent_check == "ok":
            if ks.status != LensKnowledgeSource.Status.DEGRADED:
                ks.status = LensKnowledgeSource.Status.READY
        elif agent_check:
            ks.status = LensKnowledgeSource.Status.ERROR
            ks.status_detail = str(agent_check)
        elif ks.status == LensKnowledgeSource.Status.SYNCING:
            pass
        else:
            ks.status = LensKnowledgeSource.Status.SYNCING
            ks.status_detail = ks.status_detail or "Indexing in progress…"
    ks.save(update_fields=["status", "status_detail", "updated_at"])
    return ks


def ensure_lensnode_for_gateway(
    *,
    org: Organization,
    gateway: Node,
    name: str | None = None,
    owner_user=None,
    scope: str = "",
) -> LensGatewayLink:
    """Idempotently associate a SourceLens LensNode with an HFL data gateway."""
    if gateway.role != NodeRole.GATEWAY:
        raise ValidationError({"gateway_id": "Node is not a data gateway."})

    normalized_scope = (scope or "").strip().lower()
    is_platform = normalized_scope == LensGatewayLink.GatewayScope.PLATFORM
    desired_scope = (
        LensGatewayLink.GatewayScope.PLATFORM
        if is_platform
        else LensGatewayLink.GatewayScope.USER
    )
    desired_origin = (
        LensGatewayLink.Origin.PLATFORM if is_platform else LensGatewayLink.Origin.USER
    )
    link, created = LensGatewayLink.objects.get_or_create(
        organization=org,
        gateway=gateway,
        defaults={
            "workspace_root": f"/workspace/org-{org.id}",
            "owner_user": None if is_platform else owner_user,
            "scope": desired_scope,
            "origin": desired_origin,
        },
    )

    if not created:
        update_fields = []
        if link.scope != desired_scope:
            link.scope = desired_scope
            update_fields.append("scope")
        if link.origin != desired_origin:
            link.origin = desired_origin
            update_fields.append("origin")
        if not is_platform and owner_user is not None and link.owner_user_id is None:
            link.owner_user = owner_user
            update_fields.append("owner_user")
        if update_fields:
            link.save(update_fields=[*update_fields, "updated_at"])

    if is_platform and not link.is_platform_default:
        from apps.node.services.internal.local_platform_gateway import (
            is_local_platform_gateway_metadata,
        )

        has_platform_default = LensGatewayLink.objects.filter(
            organization=org,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
            is_platform_default=True,
        ).exclude(pk=link.pk).exists()
        if is_local_platform_gateway_metadata(gateway.metadata) and not has_platform_default:
            link.is_platform_default = True
            link.save(update_fields=["is_platform_default", "updated_at"])

    if link.sl_lensnode_uuid:
        return link

    node_name = name or f"hfl-gw-{gateway.id}-{gateway.name}"[:160]
    data = sl_client.request_json(
        "POST",
        "/api/lens/admin/lensnodes/",
        json_body={"name": node_name},
    )
    lensnode_uuid = data.get("uuid")
    token = data.get("token")
    if not lensnode_uuid:
        raise sl_client.LensBridgeError("LensNode create returned no uuid.")

    config = dict(link.config_json or {})
    if token:
        config["lensnode_token_issued"] = True
        config["lensnode_token"] = token

    link.sl_lensnode_uuid = uuid.UUID(str(lensnode_uuid))
    link.sidecar_status = LensGatewayLink.SidecarStatus.OFFLINE
    link.config_json = config
    link.save(
        update_fields=[
            "sl_lensnode_uuid",
            "sidecar_status",
            "config_json",
            "updated_at",
        ]
    )
    return link


def enable_ai_on_gateway(
    *,
    org: Organization,
    gateway: Node,
    name: str | None = None,
    scope: str | None = None,
) -> LensGatewayLink:
    link = ensure_lensnode_for_gateway(
        org=org,
        gateway=gateway,
        name=name,
        scope=scope or "",
    )
    if scope:
        desired = scope.strip().lower()
        if desired in (
            LensGatewayLink.GatewayScope.PLATFORM,
            LensGatewayLink.GatewayScope.USER,
        ):
            if link.scope != desired:
                link.scope = desired
                link.save(update_fields=["scope", "updated_at"])
    return link


def build_lens_enroll_config(link: LensGatewayLink) -> dict[str, Any]:
    """LensNode credentials for gateway enrollment / sidecar install."""
    from apps.lens_bridge.deploy import lens_gateway_base_url

    config = link.config_json or {}
    gateway = link.gateway
    lensnode_name = f"hfl-gw-{gateway.id}-{gateway.name}"[:160]
    return {
        "lens_base_url": lens_gateway_base_url(),
        "lensnode_uuid": str(link.sl_lensnode_uuid) if link.sl_lensnode_uuid else None,
        "lensnode_token": config.get("lensnode_token"),
        "lensnode_name": lensnode_name,
        "workspace_root": link.resolved_workspace_root(),
    }


def provision_gateway_lens_on_register(
    *,
    org: Organization,
    gateway: Node,
    owner_user=None,
    scope: str = "",
) -> dict[str, Any] | None:
    """Auto-provision LensNode when a gateway registers; returns enroll config or None."""
    from apps.lens_bridge.deploy import lens_bridge_configured

    if gateway.role != NodeRole.GATEWAY or not lens_bridge_configured():
        return None
    try:
        link = ensure_lensnode_for_gateway(
            org=org,
            gateway=gateway,
            owner_user=owner_user,
            scope=scope,
        )
        return build_lens_enroll_config(link)
    except Exception:
        logger.warning(
            "gateway lens provision failed gateway_id=%s",
            gateway.id,
            exc_info=True,
        )
        return None


def record_gateway_install_status(
    *,
    org: Organization,
    gateway: Node,
    status: str,
    error_message: str = "",
    phase: str = "install",
) -> LensGatewayLink | None:
    """Update sidecar status when gateway lifecycle reports progress."""
    if gateway.role != NodeRole.GATEWAY:
        return None

    phase = str(phase or "install").strip().lower()
    status = str(status or "").strip().lower()

    link = LensGatewayLink.objects.filter(organization=org, gateway=gateway).first()
    if link is None and status == "failed":
        link, _ = LensGatewayLink.objects.get_or_create(
            organization=org,
            gateway=gateway,
            defaults={"workspace_root": f"/workspace/org-{org.id}"},
        )

    if link is None:
        return None

    config = dict(link.config_json or {})
    config["lifecycle_phase"] = phase
    if error_message:
        config["lifecycle_error"] = error_message[:2000]
    elif status in {"success", "running"}:
        config.pop("lifecycle_error", None)

    if status == "running":
        if phase == "sidecar_upgrade":
            link.sidecar_status = LensGatewayLink.SidecarStatus.UPGRADING
        elif phase == "sidecar_uninstall":
            link.sidecar_status = LensGatewayLink.SidecarStatus.REMOVING
        config["lifecycle_status"] = "running"
    elif status == "failed":
        link.sidecar_status = LensGatewayLink.SidecarStatus.ERROR
        config["lifecycle_status"] = "failed"
        if phase == "install":
            config["install_status"] = "failed"
            if error_message:
                config["install_error"] = error_message[:2000]
    else:
        config["lifecycle_status"] = "success"
        if phase == "install":
            config["install_status"] = "success"
            config.pop("install_error", None)
            if link.sl_lensnode_uuid and link.sidecar_status == LensGatewayLink.SidecarStatus.ERROR:
                link.sidecar_status = LensGatewayLink.SidecarStatus.OFFLINE
        elif phase == "sidecar_upgrade":
            link.sidecar_status = LensGatewayLink.SidecarStatus.OFFLINE
        elif phase == "sidecar_uninstall":
            link.sidecar_status = LensGatewayLink.SidecarStatus.NOT_DEPLOYED
            config.pop("install_status", None)

    link.config_json = config
    link.save(update_fields=["sidecar_status", "config_json", "updated_at"])
    return link


def _extract_sl_lensnode_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    tasks: list[dict[str, str]] = []
    for item in data.get("tasks") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        title = str(item.get("title") or name).strip()
        if name or title:
            tasks.append({"name": name, "title": title or name})
    uuid_raw = data.get("uuid")
    return {
        "sl_name": str(data.get("name") or "").strip(),
        "sl_lensnode_uuid": str(uuid_raw).strip() if uuid_raw else "",
        "sl_status": str(data.get("status") or "").strip(),
        "sl_workspace_path": str(data.get("workspace_path") or "").strip(),
        "sl_agent_version": str(data.get("agent_version") or "").strip(),
        "sl_last_heartbeat_at": data.get("last_heartbeat_at"),
        "sl_registered_at": data.get("registered_at"),
        "sl_tasks": tasks,
    }


def _empty_sl_lensnode_snapshot() -> dict[str, Any]:
    return {
        "sl_name": "",
        "sl_lensnode_uuid": "",
        "sl_status": "",
        "sl_workspace_path": "",
        "sl_agent_version": "",
        "sl_last_heartbeat_at": None,
        "sl_registered_at": None,
        "sl_tasks": [],
    }


def sl_lensnode_snapshot_from_link(link: LensGatewayLink | None) -> dict[str, Any]:
    if link is None:
        return _empty_sl_lensnode_snapshot()
    snap = (link.config_json or {}).get("sl_lensnode_snapshot")
    if isinstance(snap, dict) and snap:
        out = _empty_sl_lensnode_snapshot()
        out.update({k: snap.get(k, out[k]) for k in out})
        if link.sl_lensnode_uuid and not out["sl_lensnode_uuid"]:
            out["sl_lensnode_uuid"] = str(link.sl_lensnode_uuid)
        if not out["sl_workspace_path"]:
            out["sl_workspace_path"] = link.resolved_workspace_root()
        return out
    out = _empty_sl_lensnode_snapshot()
    if link.sl_lensnode_uuid:
        out["sl_lensnode_uuid"] = str(link.sl_lensnode_uuid)
    out["sl_workspace_path"] = link.resolved_workspace_root()
    return out


def build_gateway_ai_payload(
    *,
    gateway: Node,
    link: LensGatewayLink | None,
    include_token: bool = False,
) -> dict[str, Any]:
    snap = sl_lensnode_snapshot_from_link(link)
    workspace = snap.get("sl_workspace_path") or (link.resolved_workspace_root() if link else "")
    display_snap = {k: v for k, v in snap.items() if k != "sl_lensnode_uuid"}
    payload: dict[str, Any] = {
        "gateway_id": gateway.id,
        "ai_enabled": bool(link and link.sl_lensnode_uuid),
        "sidecar_status": link.sidecar_status if link else LensGatewayLink.SidecarStatus.NOT_DEPLOYED,
        "workspace_root": workspace,
        "sl_lensnode_uuid": link.sl_lensnode_uuid if link and link.sl_lensnode_uuid else None,
        **display_snap,
    }
    if include_token and link is not None:
        payload["lensnode_token"] = (link.config_json or {}).get("lensnode_token")
    return payload


def apply_gateway_lensnode_snapshot(
    link: LensGatewayLink,
    data: dict[str, Any],
) -> LensGatewayLink:
    """Persist a LensNode heartbeat payload without overriding active lifecycle work."""
    preserve_lifecycle = link.sidecar_status in (
        LensGatewayLink.SidecarStatus.REMOVING,
        LensGatewayLink.SidecarStatus.UPGRADING,
    )
    update_fields: list[str] = []
    if not preserve_lifecycle:
        sl_status = str(data.get("status") or "").lower()
        if sl_status == "online":
            next_status = LensGatewayLink.SidecarStatus.ONLINE
        elif sl_status == "offline":
            next_status = LensGatewayLink.SidecarStatus.OFFLINE
        else:
            next_status = LensGatewayLink.SidecarStatus.OFFLINE
        if link.sidecar_status != next_status:
            link.sidecar_status = next_status
            update_fields.append("sidecar_status")

    config = dict(link.config_json or {})
    snapshot = _extract_sl_lensnode_snapshot(data)
    if config.get("sl_lensnode_snapshot") != snapshot:
        config["sl_lensnode_snapshot"] = snapshot
        link.config_json = config
        update_fields.append("config_json")
    if update_fields:
        link.save(update_fields=[*update_fields, "updated_at"])
    return link


def sync_gateway_lensnode_status(link: LensGatewayLink) -> LensGatewayLink:
    if not link.sl_lensnode_uuid:
        if link.sidecar_status != LensGatewayLink.SidecarStatus.NOT_DEPLOYED:
            link.sidecar_status = LensGatewayLink.SidecarStatus.NOT_DEPLOYED
            link.save(update_fields=["sidecar_status", "updated_at"])
        return link

    try:
        data = sl_client.request_json("GET", f"/api/lens/admin/lensnodes/{link.sl_lensnode_uuid}/")
    except sl_client.LensBridgeError:
        if link.sidecar_status not in (
            LensGatewayLink.SidecarStatus.REMOVING,
            LensGatewayLink.SidecarStatus.UPGRADING,
            LensGatewayLink.SidecarStatus.ERROR,
        ):
            link.sidecar_status = LensGatewayLink.SidecarStatus.ERROR
            link.save(update_fields=["sidecar_status", "updated_at"])
        return link
    return apply_gateway_lensnode_snapshot(link, data)


def _entry_is_dir(item: dict[str, Any]) -> bool:
    if item.get("is_dir") is True:
        return True
    path_type = str(item.get("path_type") or item.get("type") or "").lower()
    if path_type in {"directory", "dir", "folder"}:
        return True
    return bool(item.get("isLeaf") is False)


def _normalize_gateway_browse_entries(raw_entries: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_entries, list):
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        is_dir = _entry_is_dir(item)
        if not is_dir:
            continue
        path = str(item.get("path") or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        name = str(item.get("name") or item.get("label") or "").strip() or path.rstrip("/").split("/")[-1]
        rows.append(
            {
                "name": name,
                "path": path,
                "type": "dir",
                "size_bytes": 0,
                "modified_at": str(item.get("mod_time") or item.get("modified_at") or "") or None,
                "downloadable": False,
                "has_children": True,
            }
        )
    return sorted(rows, key=lambda row: row["name"].lower())


def browse_gateway_directory(
    *,
    org: Organization,
    gateway_id: int,
    path: str = "",
    limit: int = 200,
    wait_timeout_seconds: int = 15,
) -> dict[str, Any]:
    import posixpath

    from apps.node.services.interface import run_agent_task_sync

    gateway = require_gateway_node(org, gateway_id)
    if gateway.status != Node.Status.ONLINE:
        raise ValidationError({"gateway": "Data gateway must be online to browse directories."})

    link, _ = LensGatewayLink.objects.get_or_create(
        organization=org,
        gateway=gateway,
        defaults={"workspace_root": f"/workspace/org-{org.id}"},
    )

    root = link.resolved_workspace_root().rstrip("/") or "/"
    browse_path = str(path or "").strip() or root
    normalized_root = root.rstrip("/") or "/"
    if browse_path != normalized_root and not browse_path.startswith(f"{normalized_root}/"):
        raise ValidationError({"path": "Path must be under the gateway workspace root."})

    outcome = run_agent_task_sync(
        organization_id=org.id,
        node_id=gateway.id,
        kind="explorer.list",
        payload={
            "path": browse_path,
            "dirs_only": True,
            "include_metadata": False,
            "limit": limit,
        },
        correlation_type="lens.gateway.browse",
        correlation_id=str(gateway_id),
        wait_timeout_seconds=wait_timeout_seconds,
    )
    if outcome.timed_out:
        raise ValidationError({"detail": "Directory listing timed out."})
    if not outcome.ok:
        error = getattr(outcome.task, "last_error", "") or "Directory listing failed."
        raise ValidationError({"detail": error})

    try:
        result = outcome.result
    except (TypeError, ValueError):
        result = {}
    if not isinstance(result, dict):
        result = {}

    listed_path = str(result.get("path") or browse_path).strip() or browse_path
    parent_path = posixpath.dirname(listed_path.rstrip("/")) or normalized_root
    if parent_path != normalized_root and not parent_path.startswith(f"{normalized_root}/"):
        parent_path = normalized_root

    return {
        "gateway_id": gateway_id,
        "path": listed_path,
        "root_path": normalized_root,
        "parent_path": parent_path,
        "entries": _normalize_gateway_browse_entries(result.get("entries")),
        "has_more": bool(result.get("has_more")),
        "next_cursor": str(result.get("next_cursor") or ""),
    }
