"""Chat 1:1 lifecycle — each New Chat owns restore+KS+Ass; delete tears them down (not DG)."""

from __future__ import annotations

import logging
import uuid as uuid_lib
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import LensChatBinding, LensKnowledgeSource, LensSessionLink
from apps.lens_bridge.services import (
    assistant_access,
    chat_user_provisioning,
    knowledge_source_sync,
    provisioning,
    sl_client,
)
from apps.lens_bridge.services.chat_binding import _grant_assistant_to_chat_user
from apps.lens_bridge.services import platform_lens
from apps.protection.models import BackupConfig, BackupSourceSnapshot, BackupSourceSnapshotDirectory
from apps.protection.services.source_identity import resolve_source_display_name

logger = logging.getLogger(__name__)


def _source_path_basename(path: str) -> str:
    normalized = path.strip().replace("\\", "/").rstrip("/")
    if not normalized or normalized.endswith(":"):
        return ""
    return normalized.rsplit("/", 1)[-1].strip()


def _unique_session_title(
    org: Organization,
    *,
    user: AbstractBaseUser,
    base_title: str,
) -> str:
    base = base_title.strip()[:160] or "New Chat"
    existing = {
        title.casefold()
        for title in LensSessionLink.objects.filter(
            organization=org,
            hfl_user=user,
            status=LensSessionLink.Status.ACTIVE,
        ).values_list("title", flat=True)
        if title
    }
    if base.casefold() not in existing:
        return base
    suffix_number = 2
    while True:
        suffix = f" ({suffix_number})"
        candidate = f"{base[: 160 - len(suffix)]}{suffix}"
        if candidate.casefold() not in existing:
            return candidate
        suffix_number += 1


def _default_session_title(
    org: Organization,
    *,
    user: AbstractBaseUser,
    source_name: str | None,
    source_scopes: list[dict[str, Any]],
) -> str:
    source_label = (source_name or "").strip() or "New Chat"
    first_item = _source_path_basename(str(source_scopes[0].get("source_path") or ""))
    base_title = first_item or source_label
    if len(source_scopes) > 1:
        base_title = f"{base_title} +{len(source_scopes) - 1}"
    return _unique_session_title(org, user=user, base_title=base_title)


def start_copilot_chat(
    org: Organization,
    *,
    user: AbstractBaseUser,
    binding: LensChatBinding,
    title: str | None = None,
) -> LensSessionLink:
    """Legacy adapter for old clients that still submit a prepared binding."""
    if not binding.gateway_link_id:
        raise ValidationError({"gateway_link_id": "Data gateway is required."})
    scopes = [{
        "source_path": binding.source_path,
        "backup_snapshot_directory_id": binding.backup_snapshot_directory_id,
        "path_type": "unknown",
    }]
    link = create_copilot_chat(
        org,
        user=user,
        backup_config_id=binding.backup_config_id,
        backup_source_snapshot_id=binding.backup_source_snapshot_id,
        source_scopes=scopes,
        gateway_mode=LensSessionLink.GatewaySelectionMode.MANUAL,
        gateway_link_id=binding.gateway_link_id,
        title=title,
    )
    link.chat_binding = binding
    link.save(update_fields=["chat_binding", "updated_at"])
    return link


@transaction.atomic
def create_copilot_chat(
    org: Organization,
    *,
    user: AbstractBaseUser,
    backup_config_id: int,
    backup_source_snapshot_id: int,
    source_scopes: list[dict[str, Any]],
    gateway_mode: str,
    gateway_link_id: int | None,
    title: str | None = None,
) -> LensSessionLink:
    """Create the local Chat shell; all SourceLens resources are asynchronous."""
    config = BackupConfig.objects.filter(id=backup_config_id, organization_id=org.id).first()
    if config is None:
        raise ValidationError({"backup_config_id": "Backup source not found."})
    snapshot = BackupSourceSnapshot.objects.filter(
        id=backup_source_snapshot_id,
        organization_id=org.id,
        backup_config_id=config.id,
    ).first()
    if snapshot is None:
        raise ValidationError({"backup_source_snapshot_id": "Snapshot not found for this backup source."})

    normalized_scopes: list[dict[str, Any]] = []
    for index, scope in enumerate(source_scopes):
        path = str(scope.get("source_path") or "").strip()
        directory_id = scope.get("backup_snapshot_directory_id")
        directory = BackupSourceSnapshotDirectory.objects.filter(
            id=directory_id,
            source_snapshot_id=snapshot.id,
            status=BackupSourceSnapshotDirectory.Status.AVAILABLE,
        ).first()
        if not path or directory is None:
            raise ValidationError({"source_scopes": {index: "Select a valid file or directory from this snapshot."}})
        normalized_scopes.append(
            {
                "source_path": path,
                "backup_snapshot_directory_id": directory.id,
                "path_type": str(scope.get("path_type") or "unknown"),
            }
        )
    if not normalized_scopes:
        raise ValidationError({"source_scopes": "Select at least one file or folder."})

    if gateway_mode == LensSessionLink.GatewaySelectionMode.AUTO:
        gateway_link = platform_lens.resolve_auto_gateway_link_for_copilot(user=user)
    else:
        gateway_link = platform_lens.resolve_gateway_link_for_copilot(
            org,
            user=user,
            gateway_link_id=gateway_link_id,
        )
    if gateway_link is None:
        raise ValidationError(
            {
                "gateway_link_id": (
                    "No platform gateway is available. Select a private gateway or contact your administrator."
                )
            }
        )

    from apps.lens_bridge.services.gateway_readiness import require_copilot_gateway

    require_copilot_gateway(gateway_link)
    model_ref = provisioning.default_model_ref_for_org(org)
    if not model_ref:
        raise ValidationError({"model": "Configure an active AI model before creating a chat."})

    source_display_name = resolve_source_display_name(
        organization_id=org.id,
        source_type=config.source_type,
        source_ref_id=config.source_ref_id,
        fallback=config.name,
    )
    default_title = _default_session_title(
        org,
        user=user,
        source_name=source_display_name,
        source_scopes=normalized_scopes,
    )
    link = LensSessionLink.objects.create(
        organization=org,
        hfl_user=user,
        title=(title or "").strip() or default_title,
        backup_config_id=config.id,
        backup_source_snapshot_id=snapshot.id,
        source_scopes_json=normalized_scopes,
        gateway_link=gateway_link,
        gateway_selection_mode=gateway_mode,
        agent_model_ref=model_ref,
        status=LensSessionLink.Status.ACTIVE,
        lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
        provision_phase=LensSessionLink.ProvisionPhase.QUEUED,
        provision_detail="Chat creation is queued.",
        lifecycle_error="",
    )

    transaction.on_commit(lambda: _queue_provision_or_mark_failed(link.id))
    return link


def request_copilot_chat_teardown(link: LensSessionLink) -> LensSessionLink:
    """Mark chat deleting and enqueue teardown. Never touches DG."""
    if link.lifecycle_status == LensSessionLink.LifecycleStatus.DELETED:
        return link

    if link.lifecycle_status == LensSessionLink.LifecycleStatus.DELETING:
        _queue_teardown_or_record_error(link.id)
        return link

    link.lifecycle_status = LensSessionLink.LifecycleStatus.DELETING
    link.provision_phase = LensSessionLink.ProvisionPhase.DELETING
    link.provision_detail = "Deleting chat resources."
    link.lifecycle_error = ""
    link.status = LensSessionLink.Status.ARCHIVED
    link.save(update_fields=["lifecycle_status", "provision_phase", "provision_detail", "lifecycle_error", "status", "updated_at"])


    _queue_teardown_or_record_error(link.id)
    return link


def run_copilot_chat_provision(*, session_link_id: int) -> dict[str, Any]:
    """Provision one chat and persist failures from every execution stage."""
    try:
        return _run_copilot_chat_provision(session_link_id=session_link_id)
    except Exception as exc:
        logger.exception(
            "copilot chat provision failed session_link_id=%s",
            session_link_id,
        )
        _mark_provision_failed_by_id(session_link_id, str(exc))
        raise


def _run_copilot_chat_provision(*, session_link_id: int) -> dict[str, Any]:
    link = (
        LensSessionLink.objects.select_related(
            "chat_binding",
            "chat_binding__gateway_link",
            "chat_binding__gateway_link__gateway",
            "gateway_link",
            "gateway_link__gateway",
            "hfl_user",
            "organization",
        )
        .filter(pk=session_link_id)
        .first()
    )
    if link is None:
        raise ValidationError({"session": "Session not found."})
    if link.lifecycle_status == LensSessionLink.LifecycleStatus.READY and link.sl_session_uuid:
        return {"session_link_id": link.id, "status": "ready"}
    if link.lifecycle_status == LensSessionLink.LifecycleStatus.DELETING:
        return {"session_link_id": link.id, "status": "deleting"}

    binding = link.chat_binding
    gateway_link = link.gateway_link or (binding.gateway_link if binding else None)
    if gateway_link is None:
        _mark_failed(link, "Data gateway is missing.")
        raise ValidationError({"gateway_link": "Data gateway is missing."})
    scopes = list(link.source_scopes_json or [])
    if not scopes and binding is not None:
        scopes = [{
            "source_path": binding.source_path,
            "backup_snapshot_directory_id": binding.backup_snapshot_directory_id,
            "path_type": "unknown",
        }]
    if not scopes:
        _mark_failed(link, "Backup content selection is missing.")
        raise ValidationError({"source_scopes": "Backup content selection is missing."})
    snapshot_id = link.backup_source_snapshot_id or (binding.backup_source_snapshot_id if binding else None)
    if not snapshot_id:
        _mark_failed(link, "Backup snapshot is missing.")
        raise ValidationError({"backup_source_snapshot_id": "Backup snapshot is missing."})
    org = link.organization
    user = link.hfl_user

    try:
        _set_phase(link, LensSessionLink.ProvisionPhase.RESTORING, "Restoring selected backup data.")
        sl_user_link = chat_user_provisioning.ensure_sl_chat_user(user)

        # 1) Always create a fresh KS for this chat (no reuse).
        ks = link.knowledge_source
        if ks is None:
            first_path = str(scopes[0].get("source_path") or "Copilot")
            ks_name = f"{first_path.rstrip('/').split('/')[-1] or 'Copilot'} · Chat {link.id}"
            first_directory_id = scopes[0].get("backup_snapshot_directory_id")
            ks = LensKnowledgeSource.objects.create(
                organization=org,
                name=ks_name[:160],
                gateway=gateway_link.gateway,
                backup_source_snapshot_id=snapshot_id,
                backup_snapshot_directory_id=first_directory_id,
                source_path=first_path,
                source_scopes_json=scopes,
                sl_lensnode_uuid=gateway_link.sl_lensnode_uuid,
                created_by=user,
            )
            ks = knowledge_source_sync.prepare_new_knowledge_source(org=org, ks=ks)
            link.knowledge_source = ks
            link.save(update_fields=["knowledge_source", "updated_at"])

        # 2) Restore + index synchronously inside this worker (DG unchanged).
        sync_result = knowledge_source_sync.run_knowledge_source_sync(
            organization_id=org.id,
            knowledge_source_id=ks.id,
        )
        ks.refresh_from_db()
        if ks.status not in (
            LensKnowledgeSource.Status.READY,
            LensKnowledgeSource.Status.DEGRADED,
        ):
            raise ValidationError(
                {"knowledge_source": f"Knowledge source sync did not complete ({ks.status})."}
            )

        # 3) Create Assistant (SL Admin) and grant to Chat User.
        _set_phase(
            link,
            LensSessionLink.ProvisionPhase.CREATING_KNOWLEDGE_SOURCE,
            "Finalizing the private knowledge source.",
        )
        _set_phase(link, LensSessionLink.ProvisionPhase.CREATING_ASSISTANT, "Creating the private assistant.")
        assistant_uuid = link.sl_assistant_uuid or ks.sl_assistant_uuid
        if assistant_uuid is None:
            assistant_uuid = provisioning.create_sl_assistant_for_ks(
                org=org,
                ks=ks,
                gateway_link=gateway_link,
                model_ref=link.agent_model_ref,
            )
            ks.sl_assistant_uuid = assistant_uuid
            ks.save(update_fields=["sl_assistant_uuid", "updated_at"])
            link.sl_assistant_uuid = assistant_uuid
            link.save(update_fields=["sl_assistant_uuid", "updated_at"])
        assistant_access.ensure_assistant_link(
            org=org,
            sl_assistant_uuid=assistant_uuid,
            knowledge_source=ks,
            created_by=user,
            owner_user=user,
            visibility_scope="user",
        )
        _set_phase(link, LensSessionLink.ProvisionPhase.GRANTING_ASSISTANT, "Granting assistant access.")
        _grant_assistant_to_chat_user(assistant_uuid=assistant_uuid, sl_user_id=sl_user_link.sl_user_id)

        # 4) Create SL session as Chat User.
        _set_phase(link, LensSessionLink.ProvisionPhase.CREATING_SESSION, "Opening the chat session.")
        session_uuid = link.sl_session_uuid
        if session_uuid is None:
            sl_session = sl_client.request_json(
                "POST",
                "/api/lens/sessions/",
                json_body={"assistant_uuid": str(assistant_uuid), "title": link.title},
                hfl_user=user,
            )
            session_uuid = uuid_lib.UUID(str(sl_session["uuid"]))

        link.sl_assistant_uuid = assistant_uuid
        link.sl_session_uuid = session_uuid
        link.lifecycle_status = LensSessionLink.LifecycleStatus.READY
        link.provision_phase = LensSessionLink.ProvisionPhase.READY
        link.provision_detail = "Chat is ready."
        link.lifecycle_error = ""
        ks.status = LensKnowledgeSource.Status.READY
        ks.status_detail = "Restored data and Assistant are ready for chat."
        ks.save(update_fields=["status", "status_detail", "updated_at"])
        link.save(
            update_fields=[
                "sl_assistant_uuid",
                "sl_session_uuid",
                "lifecycle_status",
                "provision_phase",
                "provision_detail",
                "lifecycle_error",
                "updated_at",
            ]
        )
        return {
            "session_link_id": link.id,
            "status": "ready",
            "knowledge_source_id": ks.id,
            "sync": sync_result,
        }
    except Exception as exc:
        logger.exception("copilot chat provision failed session_link_id=%s", session_link_id)
        _cleanup_failed_provision(link)
        _mark_failed(link, str(exc))
        raise


def run_copilot_chat_teardown(*, session_link_id: int) -> dict[str, Any]:
    link = (
        LensSessionLink.objects.select_related(
            "knowledge_source",
            "hfl_user",
            "organization",
            "chat_binding",
        )
        .filter(pk=session_link_id)
        .first()
    )
    if link is None:
        return {"session_link_id": session_link_id, "status": "missing"}
    if link.lifecycle_status == LensSessionLink.LifecycleStatus.DELETED:
        return {"session_link_id": link.id, "status": "deleted"}

    org = link.organization
    user = link.hfl_user
    errors: list[str] = []

    # Cancel active run (best-effort).
    if link.active_run_uuid:
        try:
            sl_client.request_json(
                "POST",
                f"/api/lens/runs/{link.active_run_uuid}/cancel/",
                hfl_user=user,
            )
        except Exception as exc:
            errors.append(f"cancel_run: {exc}")

    # Delete SL session (Chat User). Never touches DG.
    if link.sl_session_uuid:
        try:
            sl_client.request_json(
                "DELETE",
                f"/api/lens/sessions/{link.sl_session_uuid}/",
                hfl_user=user,
            )
        except Exception as exc:
            errors.append(f"delete_session: {exc}")

    assistant_uuid = link.sl_assistant_uuid
    ks = link.knowledge_source

    # Delete SL Assistant (Admin token) — real DELETE, then HFL link cleanup.
    if assistant_uuid:
        try:
            from apps.lens_bridge.services.assistants import _delete_sl_assistant

            _delete_sl_assistant(assistant_uuid)
        except Exception as exc:
            errors.append(f"delete_assistant_sl: {exc}")
        try:
            assistant_access.soft_delete_assistant_link(org, assistant_uuid)
        except Exception as exc:
            errors.append(f"delete_assistant_link: {exc}")

    # Soft-delete KS owned by this chat. DG itself is never deleted.
    if ks is not None:
        try:
            _cleanup_ks_workspace_marker(ks)
            if ks.sl_assistant_uuid == assistant_uuid:
                ks.sl_assistant_uuid = None
                ks.save(update_fields=["sl_assistant_uuid", "updated_at"])
            ks.soft_delete()
        except Exception as exc:
            errors.append(f"delete_ks: {exc}")

    link.lifecycle_status = LensSessionLink.LifecycleStatus.DELETED
    link.status = LensSessionLink.Status.ARCHIVED
    link.provision_phase = LensSessionLink.ProvisionPhase.DELETED
    link.provision_detail = "Chat resources deleted."
    link.lifecycle_error = "; ".join(errors)[:2000]
    link.active_run_uuid = None
    link.active_run_status = ""
    link.save(
        update_fields=[
            "lifecycle_status",
            "status",
            "provision_phase",
            "provision_detail",
            "lifecycle_error",
            "active_run_uuid",
            "active_run_status",
            "updated_at",
        ]
    )
    return {
        "session_link_id": link.id,
        "status": "deleted",
        "errors": errors,
        # Explicit: DG lifecycle is independent of chat teardown.
        "gateway_untouched": True,
    }


def _cleanup_ks_workspace_marker(ks: LensKnowledgeSource) -> None:
    """Mark KS workspace for cleanup without touching the DG itself.

    Full agent-side RemoveAll for ``lens.ks.cleanup`` can land later; record
    intent so ops/reconcile jobs can reclaim {workspace_root}/ks-{id}.
    """
    sync_state = dict(ks.sync_state_json or {})
    sync_state["teardown_requested_at"] = timezone.now().isoformat()
    sync_state["teardown_workspace_path"] = ks.workspace_path_on_lensnode or ""
    ks.sync_state_json = sync_state
    ks.save(update_fields=["sync_state_json", "updated_at"])


def _mark_failed(link: LensSessionLink, message: str) -> None:
    link.lifecycle_status = LensSessionLink.LifecycleStatus.FAILED
    link.provision_phase = LensSessionLink.ProvisionPhase.QUEUED
    link.provision_detail = "Chat preparation failed."
    link.lifecycle_error = (message or "provision failed")[:2000]
    link.save(update_fields=["lifecycle_status", "provision_phase", "provision_detail", "lifecycle_error", "updated_at"])


def _mark_provision_failed_by_id(session_link_id: int, message: str) -> None:
    LensSessionLink.objects.filter(pk=session_link_id).exclude(
        lifecycle_status__in=(
            LensSessionLink.LifecycleStatus.DELETING,
            LensSessionLink.LifecycleStatus.DELETED,
        )
    ).update(
        lifecycle_status=LensSessionLink.LifecycleStatus.FAILED,
        provision_phase=LensSessionLink.ProvisionPhase.QUEUED,
        provision_detail="Chat preparation failed.",
        lifecycle_error=(message or "provision failed")[:2000],
        updated_at=timezone.now(),
    )


def _set_phase(link: LensSessionLink, phase: str, detail: str) -> None:
    link.refresh_from_db(fields=["lifecycle_status"])
    if link.lifecycle_status == LensSessionLink.LifecycleStatus.DELETING:
        raise ValidationError({"lifecycle_status": "Chat deletion was requested."})
    link.provision_phase = phase
    link.provision_detail = detail[:300]
    link.save(update_fields=["provision_phase", "provision_detail", "updated_at"])


@transaction.atomic
def retry_copilot_chat_provision(link: LensSessionLink) -> LensSessionLink:
    locked = LensSessionLink.objects.select_for_update().get(pk=link.pk)
    if locked.lifecycle_status in (
        LensSessionLink.LifecycleStatus.READY,
        LensSessionLink.LifecycleStatus.PROVISIONING,
    ):
        return locked
    if locked.lifecycle_status != LensSessionLink.LifecycleStatus.FAILED:
        raise ValidationError({"lifecycle_status": "Session is not retryable."})
    locked.lifecycle_status = LensSessionLink.LifecycleStatus.PROVISIONING
    locked.provision_phase = LensSessionLink.ProvisionPhase.QUEUED
    locked.provision_detail = "Chat creation is queued."
    locked.lifecycle_error = ""
    locked.save(update_fields=["lifecycle_status", "provision_phase", "provision_detail", "lifecycle_error", "updated_at"])
    transaction.on_commit(lambda: _queue_provision_or_mark_failed(locked.id))
    return locked


def _queue_provision_or_mark_failed(session_link_id: int) -> None:
    from apps.lens_bridge.services.sync_queue import queue_copilot_chat_provision

    try:
        queue_copilot_chat_provision(session_link_id=session_link_id)
    except Exception as exc:
        logger.exception("copilot chat provision dispatch failed session_link_id=%s", session_link_id)
        LensSessionLink.objects.filter(
            pk=session_link_id,
            lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
        ).update(
            lifecycle_status=LensSessionLink.LifecycleStatus.FAILED,
            provision_phase=LensSessionLink.ProvisionPhase.QUEUED,
            provision_detail="Chat preparation could not be queued. Retry when the worker is available.",
            lifecycle_error=str(exc)[:2000],
            updated_at=timezone.now(),
        )


def _queue_teardown_or_record_error(session_link_id: int) -> None:
    from apps.lens_bridge.services.sync_queue import queue_copilot_chat_teardown

    try:
        queue_copilot_chat_teardown(session_link_id=session_link_id)
    except Exception as exc:
        logger.exception("copilot chat teardown dispatch failed session_link_id=%s", session_link_id)
        LensSessionLink.objects.filter(
            pk=session_link_id,
            lifecycle_status=LensSessionLink.LifecycleStatus.DELETING,
        ).update(
            lifecycle_error=("Teardown queue unavailable: " + str(exc))[:2000],
            provision_detail="Deletion is waiting for the worker queue.",
            updated_at=timezone.now(),
        )


def _cleanup_failed_provision(link: LensSessionLink) -> None:
    """Best-effort compensation before a failed chat can be retried.

    The identifiers are retained when a remote deletion fails, allowing a
    retry to resume rather than create another orphaned SourceLens resource.
    """
    _set_phase(link, LensSessionLink.ProvisionPhase.CLEANING_UP, "Cleaning up incomplete chat resources.")
    errors: list[str] = []
    if link.sl_session_uuid:
        try:
            sl_client.request_json("DELETE", f"/api/lens/sessions/{link.sl_session_uuid}/", hfl_user=link.hfl_user)
            link.sl_session_uuid = None
        except Exception as exc:
            errors.append(f"delete_session: {exc}")
    if link.sl_assistant_uuid:
        try:
            from apps.lens_bridge.services.assistants import _delete_sl_assistant

            _delete_sl_assistant(link.sl_assistant_uuid)
            assistant_access.soft_delete_assistant_link(link.organization, link.sl_assistant_uuid)
            link.sl_assistant_uuid = None
        except Exception as exc:
            errors.append(f"delete_assistant: {exc}")
    if link.knowledge_source_id:
        try:
            ks = link.knowledge_source
            if ks is not None:
                _cleanup_ks_workspace_marker(ks)
                ks.soft_delete()
            link.knowledge_source = None
        except Exception as exc:
            errors.append(f"delete_knowledge_source: {exc}")
    link.save(update_fields=["sl_session_uuid", "sl_assistant_uuid", "knowledge_source", "updated_at"])
    if errors:
        logger.warning("partial Copilot cleanup session_link_id=%s errors=%s", link.id, errors)
