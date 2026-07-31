"""Chat 1:1 lifecycle — each New Chat owns restore+KS+Ass; delete tears them down (not DG)."""

from __future__ import annotations

import logging
import uuid as uuid_lib
from datetime import timedelta
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import (
    LensAssistantLink,
    LensChatBinding,
    LensKnowledgeSource,
    LensSessionLink,
)
from apps.lens_bridge.services import (
    assistant_access,
    chat_user_provisioning,
    knowledge_source_sync,
    platform_lens,
    provisioning,
    sl_client,
)
from apps.lens_bridge.services.chat_binding import _grant_assistant_to_chat_user
from apps.lens_bridge.services.teardown_claims import (
    PROVISION_CLAIM_TTL_SECONDS,
    TEARDOWN_CLAIM_TTL_SECONDS,
    next_retry_at,
)
from apps.protection.models import BackupConfig, BackupSourceSnapshot, BackupSourceSnapshotDirectory
from apps.protection.services.source_identity import resolve_source_display_name

logger = logging.getLogger(__name__)

_ASSISTANT_CREATE_OPERATION = "assistant_create"
_SESSION_CREATE_OPERATION = "session_create"


class ChatProvisionLeaseLostError(RuntimeError):
    """Raised when provisioning no longer owns the Chat lifecycle lease."""


class ChatTeardownIncompleteError(RuntimeError):
    """Raised after durable teardown state is saved so Celery retries it."""


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

    from apps.lens_bridge.services.gateway_execution import context_for_gateway_link

    context_for_gateway_link(
        tenant_organization=org,
        gateway_link=gateway_link,
        expected_owner_user_id=(
            user.id
            if gateway_link.scope == gateway_link.GatewayScope.USER
            else None
        ),
    )
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


@transaction.atomic
def request_copilot_chat_teardown(link: LensSessionLink) -> LensSessionLink:
    """Mark chat deleting and enqueue teardown. Never touches DG."""
    locked = LensSessionLink.objects.select_for_update().get(pk=link.pk)
    if locked.lifecycle_status == LensSessionLink.LifecycleStatus.DELETED:
        return locked

    if locked.lifecycle_status != LensSessionLink.LifecycleStatus.DELETING:
        locked.lifecycle_status = LensSessionLink.LifecycleStatus.DELETING
        locked.provision_phase = LensSessionLink.ProvisionPhase.DELETING
        locked.provision_detail = "Deleting chat resources."
        locked.lifecycle_error = ""
        locked.status = LensSessionLink.Status.ARCHIVED
        locked.provision_claim_token = None
        locked.provision_claimed_at = None
        locked.provision_next_retry_at = None
        locked.teardown_attempts = 0
        locked.teardown_claim_token = None
        locked.teardown_claimed_at = None
        locked.teardown_next_retry_at = None
        locked.teardown_state_json = {}
        locked.save(
            update_fields=[
                "lifecycle_status",
                "provision_phase",
                "provision_detail",
                "lifecycle_error",
                "status",
                "provision_claim_token",
                "provision_claimed_at",
                "provision_next_retry_at",
                "teardown_attempts",
                "teardown_claim_token",
                "teardown_claimed_at",
                "teardown_next_retry_at",
                "teardown_state_json",
                "updated_at",
            ]
        )
    transaction.on_commit(lambda: _queue_teardown_or_record_error(locked.id))
    return locked


def _claim_copilot_chat_provision(
    session_link_id: int,
) -> tuple[str | None, str]:
    """Claim one queued or stale Chat provisioning execution."""
    now = timezone.now()
    with transaction.atomic():
        link = (
            LensSessionLink.objects.select_for_update()
            .filter(pk=session_link_id)
            .first()
        )
        if link is None:
            return None, "missing"
        if link.lifecycle_status != LensSessionLink.LifecycleStatus.PROVISIONING:
            return None, str(link.lifecycle_status)
        if (
            link.provision_claimed_at
            and link.provision_claimed_at
            > now - timedelta(seconds=PROVISION_CLAIM_TTL_SECONDS)
        ):
            return None, "busy"
        if (
            link.provision_next_retry_at
            and link.provision_next_retry_at > now
        ):
            return None, "scheduled"

        claim_token = uuid_lib.uuid4()
        link.provision_attempts += 1
        link.provision_claim_token = claim_token
        link.provision_claimed_at = now
        link.provision_next_retry_at = next_retry_at(link.provision_attempts)
        link.lifecycle_error = ""
        link.save(
            update_fields=[
                "provision_attempts",
                "provision_claim_token",
                "provision_claimed_at",
                "provision_next_retry_at",
                "lifecycle_error",
                "updated_at",
            ]
        )
    return str(claim_token), "claimed"


def run_copilot_chat_provision(*, session_link_id: int) -> dict[str, Any]:
    """Provision one chat and persist failures from every execution stage."""
    claim_token, claim_status = _claim_copilot_chat_provision(session_link_id)
    if claim_token is None:
        return {"session_link_id": session_link_id, "status": claim_status}
    try:
        return _run_copilot_chat_provision(
            session_link_id=session_link_id,
            claim_token=claim_token,
        )
    except ChatProvisionLeaseLostError:
        current_status = (
            LensSessionLink.objects.filter(pk=session_link_id)
            .values_list("lifecycle_status", flat=True)
            .first()
        )
        logger.info(
            "copilot chat provision fenced session_link_id=%s status=%s",
            session_link_id,
            current_status,
        )
        return {
            "session_link_id": session_link_id,
            "status": current_status or "missing",
        }
    except Exception as exc:
        logger.exception(
            "copilot chat provision failed session_link_id=%s",
            session_link_id,
        )
        link = LensSessionLink.objects.filter(pk=session_link_id).first()
        cleanup_errors: list[str] = []
        if link is not None:
            try:
                cleanup_errors = _cleanup_failed_provision(link, claim_token)
            except ChatProvisionLeaseLostError:
                logger.info(
                    "copilot cleanup fenced session_link_id=%s",
                    session_link_id,
                )
            except Exception as cleanup_exc:
                logger.exception(
                    "copilot cleanup failed session_link_id=%s",
                    session_link_id,
                )
                cleanup_errors = [f"cleanup_failed_provision: {cleanup_exc}"]
        if cleanup_errors:
            _transition_failed_provision_to_teardown(
                session_link_id,
                claim_token,
                message=f"{exc}; {'; '.join(cleanup_errors)}",
            )
        else:
            _mark_provision_failed_by_id(session_link_id, claim_token, str(exc))
        raise


def _run_copilot_chat_provision(
    *,
    session_link_id: int,
    claim_token: str,
) -> dict[str, Any]:
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
    _require_provision_claim(link.id, claim_token)

    binding = link.chat_binding
    gateway_link = link.gateway_link or (binding.gateway_link if binding else None)
    if gateway_link is None:
        raise ValidationError({"gateway_link": "Data gateway is missing."})
    scopes = list(link.source_scopes_json or [])
    if not scopes and binding is not None:
        scopes = [{
            "source_path": binding.source_path,
            "backup_snapshot_directory_id": binding.backup_snapshot_directory_id,
            "path_type": "unknown",
        }]
    if not scopes:
        raise ValidationError({"source_scopes": "Backup content selection is missing."})
    snapshot_id = link.backup_source_snapshot_id or (binding.backup_source_snapshot_id if binding else None)
    if not snapshot_id:
        raise ValidationError({"backup_source_snapshot_id": "Backup snapshot is missing."})
    org = link.organization
    user = link.hfl_user

    _set_phase(
        link,
        claim_token,
        LensSessionLink.ProvisionPhase.RESTORING,
        "Restoring selected backup data.",
    )
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
            gateway_link=gateway_link,
            backup_source_snapshot_id=snapshot_id,
            backup_snapshot_directory_id=first_directory_id,
            source_path=first_path,
            source_scopes_json=scopes,
            sl_lensnode_uuid=gateway_link.sl_lensnode_uuid,
            created_by=user,
        )
        ks = knowledge_source_sync.prepare_new_knowledge_source(org=org, ks=ks)
        link.knowledge_source = ks
        try:
            _update_provision_claim(link, claim_token, "knowledge_source")
        except ChatProvisionLeaseLostError:
            _cleanup_orphan_knowledge_source(ks, owner_session_link_id=link.id)
            raise

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
        claim_token,
        LensSessionLink.ProvisionPhase.CREATING_KNOWLEDGE_SOURCE,
        "Finalizing the private knowledge source.",
    )
    _set_phase(
        link,
        claim_token,
        LensSessionLink.ProvisionPhase.CREATING_ASSISTANT,
        "Creating the private assistant.",
    )
    assistant_uuid = link.sl_assistant_uuid or ks.sl_assistant_uuid
    if assistant_uuid is None:
        assistant_slug = provisioning.assistant_slug_for_ks(org=org, ks=ks)
        operation = _prepare_remote_operation(
            link,
            claim_token,
            kind=_ASSISTANT_CREATE_OPERATION,
            lookup_key=assistant_slug,
        )
        stored_remote_uuid = str(operation.get("remote_uuid") or "").strip()
        assistant_uuid = (
            uuid_lib.UUID(stored_remote_uuid)
            if stored_remote_uuid
            else _find_remote_uuid(
                path="/api/lens/assistants/",
                field="slug",
                value=assistant_slug,
            )
        )
        if assistant_uuid is None:
            assistant_uuid = provisioning.create_sl_assistant_for_ks(
                org=org,
                ks=ks,
                gateway_link=gateway_link,
                model_ref=link.agent_model_ref,
                slug=assistant_slug,
            )
    try:
        _bind_assistant_to_provision_claim(
            link,
            claim_token,
            knowledge_source=ks,
            assistant_uuid=assistant_uuid,
        )
    except ChatProvisionLeaseLostError:
        _compensate_late_assistant(link.id, assistant_uuid)
        raise
    _set_phase(
        link,
        claim_token,
        LensSessionLink.ProvisionPhase.GRANTING_ASSISTANT,
        "Granting assistant access.",
    )
    _grant_assistant_to_chat_user(
        assistant_uuid=assistant_uuid,
        sl_user_id=sl_user_link.sl_user_id,
    )

    # 4) Create SL session as Chat User.
    _set_phase(
        link,
        claim_token,
        LensSessionLink.ProvisionPhase.CREATING_SESSION,
        "Opening the chat session.",
    )
    session_uuid = link.sl_session_uuid
    if session_uuid is None:
        operation = _prepare_remote_operation(
            link,
            claim_token,
            kind=_SESSION_CREATE_OPERATION,
        )
        session_marker = str(operation["lookup_key"])
        stored_remote_uuid = str(operation.get("remote_uuid") or "").strip()
        session_uuid = (
            uuid_lib.UUID(stored_remote_uuid)
            if stored_remote_uuid
            else _find_remote_uuid(
                path="/api/lens/sessions/",
                field="title",
                value=session_marker,
                hfl_user=user,
            )
        )
        if session_uuid is None:
            sl_session = sl_client.request_json(
                "POST",
                "/api/lens/sessions/",
                json_body={
                    "assistant_uuid": str(assistant_uuid),
                    "title": session_marker,
                },
                hfl_user=user,
            )
            session_uuid = uuid_lib.UUID(str(sl_session["uuid"]))
        try:
            _record_remote_operation_resource(
                link,
                claim_token,
                kind=_SESSION_CREATE_OPERATION,
                field="sl_session_uuid",
                remote_uuid=session_uuid,
            )
        except ChatProvisionLeaseLostError:
            _compensate_late_session(link.id, session_uuid, user=user)
            raise

    sl_client.request_json(
        "PATCH",
        f"/api/lens/sessions/{session_uuid}/",
        json_body={"title": link.title},
        hfl_user=user,
    )
    _require_provision_claim(link.id, claim_token)

    _complete_copilot_chat_provision(
        link_id=link.id,
        claim_token=claim_token,
        knowledge_source_id=ks.id,
        assistant_uuid=assistant_uuid,
        session_uuid=session_uuid,
    )
    return {
        "session_link_id": link.id,
        "status": "ready",
        "knowledge_source_id": ks.id,
        "sync": sync_result,
    }


def _require_provision_claim(link_id: int, claim_token: str) -> None:
    if not LensSessionLink.objects.filter(
        pk=link_id,
        lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
        provision_claim_token=claim_token,
    ).exists():
        raise ChatProvisionLeaseLostError("Chat provisioning lease was lost.")


def _update_provision_claim(
    link: LensSessionLink,
    claim_token: str,
    *fields: str,
) -> None:
    """Persist provisioning progress only while the current lease is valid."""
    now = timezone.now()
    values = {field: getattr(link, field) for field in fields}
    values.update(provision_claimed_at=now, updated_at=now)
    updated = LensSessionLink.objects.filter(
        pk=link.id,
        lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
        provision_claim_token=claim_token,
    ).update(**values)
    if updated != 1:
        raise ChatProvisionLeaseLostError("Chat provisioning lease was lost.")
    link.provision_claimed_at = now


def _remote_items(raw: Any) -> list[dict[str, Any]]:
    """Normalize SourceLens list and paginated-list responses."""
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("results", "items", "data"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = _remote_items(value)
                if nested:
                    return nested
    return []


def _prepare_remote_operation(
    link: LensSessionLink,
    claim_token: str,
    *,
    kind: str,
    lookup_key: str = "",
) -> dict[str, Any]:
    """Persist remote-create intent before SourceLens receives the request."""
    state = dict(link.provision_state_json or {})
    operation = dict(state.get(kind) or {})
    if operation.get("status") in {"compensated", "not_created"}:
        operation = {}
    if not operation:
        operation_id = uuid_lib.uuid4()
        if kind == _SESSION_CREATE_OPERATION:
            lookup_key = f"__hfl_provision_{operation_id.hex}__"
        operation = {
            "operation_id": str(operation_id),
            "kind": kind,
            "lookup_key": lookup_key,
            "remote_uuid": "",
            "status": "intent",
            "created_at": timezone.now().isoformat(),
            "updated_at": timezone.now().isoformat(),
        }
    elif lookup_key and operation.get("lookup_key") != lookup_key:
        raise RuntimeError(f"Remote operation lookup key changed for {kind}.")
    state[kind] = operation
    link.provision_state_json = state
    _update_provision_claim(link, claim_token, "provision_state_json")
    return operation


def _record_remote_operation_resource(
    link: LensSessionLink,
    claim_token: str,
    *,
    kind: str,
    field: str,
    remote_uuid: uuid_lib.UUID,
) -> None:
    """Atomically bind a returned UUID to its journal and Chat field."""
    state = dict(link.provision_state_json or {})
    operation = dict(state.get(kind) or {})
    if not operation:
        raise RuntimeError(f"Remote operation intent is missing for {kind}.")
    operation["remote_uuid"] = str(remote_uuid)
    operation["status"] = "remote_created"
    operation["updated_at"] = timezone.now().isoformat()
    state[kind] = operation
    link.provision_state_json = state
    setattr(link, field, remote_uuid)
    _update_provision_claim(
        link,
        claim_token,
        "provision_state_json",
        field,
    )


@transaction.atomic
def _bind_assistant_to_provision_claim(
    link: LensSessionLink,
    claim_token: str,
    *,
    knowledge_source: LensKnowledgeSource,
    assistant_uuid: uuid_lib.UUID,
) -> None:
    """Atomically bind Assistant ownership while provisioning owns the Chat."""

    locked = (
        LensSessionLink.objects.select_for_update()
        .select_related("organization", "hfl_user")
        .filter(
            pk=link.id,
            lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
            provision_claim_token=claim_token,
        )
        .first()
    )
    if locked is None:
        raise ChatProvisionLeaseLostError("Chat provisioning lease was lost.")
    locked_knowledge_source = (
        LensKnowledgeSource.objects.select_for_update()
        .filter(
            pk=knowledge_source.id,
            organization_id=locked.organization_id,
            lifecycle_status=LensKnowledgeSource.LifecycleStatus.READY,
        )
        .first()
    )
    if locked_knowledge_source is None:
        raise ChatProvisionLeaseLostError(
            "Knowledge Source was deleted during Chat provisioning."
        )

    state = dict(locked.provision_state_json or {})
    operation = dict(state.get(_ASSISTANT_CREATE_OPERATION) or {})
    if operation:
        recorded_uuid = str(operation.get("remote_uuid") or "").strip()
        if recorded_uuid and recorded_uuid != str(assistant_uuid):
            raise RuntimeError("Assistant create journal references another resource.")
        operation["remote_uuid"] = str(assistant_uuid)
        operation["status"] = "remote_created"
        operation["updated_at"] = timezone.now().isoformat()
        state[_ASSISTANT_CREATE_OPERATION] = operation

    locked.provision_state_json = state
    locked.sl_assistant_uuid = assistant_uuid
    locked_knowledge_source.sl_assistant_uuid = assistant_uuid
    locked_knowledge_source.save(
        update_fields=["sl_assistant_uuid", "updated_at"]
    )
    assistant_access.ensure_assistant_link(
        org=locked.organization,
        sl_assistant_uuid=assistant_uuid,
        knowledge_source=locked_knowledge_source,
        created_by=locked.hfl_user,
        owner_user=locked.hfl_user,
        visibility_scope="user",
        lifecycle_owner=LensAssistantLink.LifecycleOwner.CHAT,
    )
    now = timezone.now()
    locked.provision_claimed_at = now
    locked.save(
        update_fields=[
            "provision_state_json",
            "sl_assistant_uuid",
            "provision_claimed_at",
            "updated_at",
        ]
    )
    link.provision_state_json = state
    link.sl_assistant_uuid = assistant_uuid
    link.provision_claimed_at = now
    knowledge_source.sl_assistant_uuid = assistant_uuid


def _operation_remote_uuid(
    link: LensSessionLink,
    kind: str,
) -> uuid_lib.UUID | None:
    operation = dict((link.provision_state_json or {}).get(kind) or {})
    value = str(operation.get("remote_uuid") or "").strip()
    return uuid_lib.UUID(value) if value else None


def _set_operation_status(
    link: LensSessionLink,
    kind: str,
    *,
    status: str,
    error: str = "",
) -> None:
    state = dict(link.provision_state_json or {})
    operation = dict(state.get(kind) or {})
    if not operation:
        return
    operation["status"] = status
    operation["last_error"] = error[:1000]
    operation["updated_at"] = timezone.now().isoformat()
    state[kind] = operation
    link.provision_state_json = state


def _late_remote_uuids(
    link: LensSessionLink,
    resource_kind: str,
) -> set[uuid_lib.UUID]:
    state = dict(link.provision_state_json or {})
    return {
        uuid_lib.UUID(str(item["remote_uuid"]))
        for item in state.get("late_resources") or []
        if isinstance(item, dict)
        and item.get("kind") == resource_kind
        and item.get("remote_uuid")
    }


def _retain_failed_late_resources(
    link: LensSessionLink,
    resource_kind: str,
    failed_uuids: list[uuid_lib.UUID],
) -> None:
    state = dict(link.provision_state_json or {})
    retained = [
        item
        for item in state.get("late_resources") or []
        if isinstance(item, dict) and item.get("kind") != resource_kind
    ]
    retained.extend(
        {
            "kind": resource_kind,
            "remote_uuid": str(remote_uuid),
            "updated_at": timezone.now().isoformat(),
        }
        for remote_uuid in failed_uuids
    )
    state["late_resources"] = retained
    link.provision_state_json = state


def _find_remote_uuid(
    *,
    path: str,
    field: str,
    value: str,
    hfl_user: AbstractBaseUser | None = None,
) -> uuid_lib.UUID | None:
    page_size = 100
    seen_pages: set[tuple[str, ...]] = set()
    for page in range(1, 1001):
        raw = sl_client.request_json(
            "GET",
            path,
            params={"page": page, "page_size": page_size},
            hfl_user=hfl_user,
        )
        items = _remote_items(raw)
        matches = [
            item
            for item in items
            if str(item.get(field) or "") == value
        ]
        if len(matches) > 1:
            raise sl_client.LensBridgeError(
                f"SourceLens returned multiple {field}={value!r} resources."
            )
        if matches:
            remote_uuid = matches[0].get("uuid")
            if not remote_uuid:
                raise sl_client.LensBridgeError(
                    f"SourceLens {field}={value!r} resource has no uuid."
                )
            return uuid_lib.UUID(str(remote_uuid))
        if isinstance(raw, list) or not items or len(items) < page_size:
            return None
        signature = tuple(
            str(item.get("uuid") or item.get(field) or "")
            for item in items
        )
        if signature in seen_pages:
            raise sl_client.LensBridgeError(
                "SourceLens pagination did not advance while finding "
                f"{field}={value!r}."
            )
        seen_pages.add(signature)
    raise sl_client.LensBridgeError(
        f"SourceLens pagination limit reached while finding {field}={value!r}."
    )


def _recover_journal_resource(
    link: LensSessionLink,
    kind: str,
    *,
    hfl_user: AbstractBaseUser | None = None,
) -> uuid_lib.UUID | None:
    """Resolve an intent whose worker may have crashed after remote creation."""
    known_uuid = _operation_remote_uuid(link, kind)
    if known_uuid is not None:
        return known_uuid
    state = dict(link.provision_state_json or {})
    operation = dict(state.get(kind) or {})
    if not operation:
        return None
    lookup_key = str(operation.get("lookup_key") or "").strip()
    if not lookup_key:
        raise RuntimeError(f"Remote operation lookup key is missing for {kind}.")
    if kind == _ASSISTANT_CREATE_OPERATION:
        remote_uuid = _find_remote_uuid(
            path="/api/lens/assistants/",
            field="slug",
            value=lookup_key,
        )
    elif kind == _SESSION_CREATE_OPERATION:
        remote_uuid = _find_remote_uuid(
            path="/api/lens/sessions/",
            field="title",
            value=lookup_key,
            hfl_user=hfl_user,
        )
    else:
        raise ValueError(f"Unsupported remote operation kind: {kind}.")
    operation["status"] = "remote_created" if remote_uuid else "not_created"
    operation["remote_uuid"] = str(remote_uuid) if remote_uuid else ""
    operation["updated_at"] = timezone.now().isoformat()
    state[kind] = operation
    link.provision_state_json = state
    return remote_uuid


def _set_phase(
    link: LensSessionLink,
    claim_token: str,
    phase: str,
    detail: str,
) -> None:
    link.provision_phase = phase
    link.provision_detail = detail[:300]
    _update_provision_claim(
        link,
        claim_token,
        "provision_phase",
        "provision_detail",
    )


@transaction.atomic
def _complete_copilot_chat_provision(
    *,
    link_id: int,
    claim_token: str,
    knowledge_source_id: int,
    assistant_uuid: uuid_lib.UUID,
    session_uuid: uuid_lib.UUID,
) -> None:
    """Commit READY only if provisioning still owns the lifecycle lease."""
    link = (
        LensSessionLink.objects.select_for_update()
        .filter(
            pk=link_id,
            lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
            provision_claim_token=claim_token,
        )
        .first()
    )
    if link is None:
        raise ChatProvisionLeaseLostError("Chat provisioning lease was lost.")
    if link.knowledge_source_id != knowledge_source_id:
        raise RuntimeError("Chat knowledge source changed during provisioning.")
    updated_ks = LensKnowledgeSource.objects.filter(
        pk=knowledge_source_id,
        lifecycle_status=LensKnowledgeSource.LifecycleStatus.READY,
    ).update(
        status=LensKnowledgeSource.Status.READY,
        status_detail="Restored data and Assistant are ready for chat.",
        updated_at=timezone.now(),
    )
    if updated_ks != 1:
        raise ChatProvisionLeaseLostError(
            "Knowledge Source was deleted during Chat provisioning."
        )
    link.sl_assistant_uuid = assistant_uuid
    link.sl_session_uuid = session_uuid
    link.lifecycle_status = LensSessionLink.LifecycleStatus.READY
    link.provision_phase = LensSessionLink.ProvisionPhase.READY
    link.provision_detail = "Chat is ready."
    link.lifecycle_error = ""
    provision_state = dict(link.provision_state_json or {})
    for kind in (_ASSISTANT_CREATE_OPERATION, _SESSION_CREATE_OPERATION):
        operation = dict(provision_state.get(kind) or {})
        if operation:
            operation["status"] = "bound"
            operation["updated_at"] = timezone.now().isoformat()
            provision_state[kind] = operation
    link.provision_state_json = provision_state
    link.provision_claim_token = None
    link.provision_claimed_at = None
    link.provision_next_retry_at = None
    link.save(
        update_fields=[
            "sl_assistant_uuid",
            "sl_session_uuid",
            "lifecycle_status",
            "provision_phase",
            "provision_detail",
            "lifecycle_error",
            "provision_state_json",
            "provision_claim_token",
            "provision_claimed_at",
            "provision_next_retry_at",
            "updated_at",
        ]
    )


def _cleanup_orphan_knowledge_source(
    knowledge_source: LensKnowledgeSource,
    *,
    owner_session_link_id: int,
) -> None:
    """Durably tear down a KS that could not be attached to its Chat."""
    try:
        from apps.lens_bridge.services.knowledge_source_teardown import (
            request_knowledge_source_teardown,
            run_knowledge_source_teardown,
        )

        request_knowledge_source_teardown(knowledge_source)
        run_knowledge_source_teardown(
            knowledge_source_id=knowledge_source.id,
            owner_session_link_id=owner_session_link_id,
        )
    except Exception:
        logger.exception(
            "orphan knowledge source cleanup deferred knowledge_source_id=%s",
            knowledge_source.id,
        )


@transaction.atomic
def _record_late_source_lens_resource(
    link_id: int,
    *,
    field: str,
    resource_uuid: uuid_lib.UUID,
    error: str,
) -> None:
    """Reopen teardown when immediate compensation cannot delete a late resource."""
    if field not in {"sl_session_uuid", "sl_assistant_uuid"}:
        raise ValueError("Unsupported late SourceLens resource field.")
    link = LensSessionLink.objects.select_for_update().get(pk=link_id)
    existing = getattr(link, field)
    if existing not in {None, resource_uuid}:
        resource_kind = (
            "session" if field == "sl_session_uuid" else "assistant"
        )
        late_resources = _late_remote_uuids(link, resource_kind)
        late_resources.add(resource_uuid)
        _retain_failed_late_resources(
            link,
            resource_kind,
            sorted(late_resources, key=str),
        )
        update_fields = [
            "provision_state_json",
            "lifecycle_error",
            "updated_at",
        ]
    else:
        setattr(link, field, resource_uuid)
        update_fields = [field, "lifecycle_error", "updated_at"]
    link.lifecycle_error = error[:2000]
    if link.lifecycle_status != LensSessionLink.LifecycleStatus.DELETING:
        link.lifecycle_status = LensSessionLink.LifecycleStatus.DELETING
        link.status = LensSessionLink.Status.ARCHIVED
        link.provision_phase = LensSessionLink.ProvisionPhase.CLEANING_UP
        link.provision_detail = "Deleting a resource returned after Chat deletion."
        link.provision_claim_token = None
        link.provision_claimed_at = None
        link.provision_next_retry_at = None
        link.teardown_claim_token = None
        link.teardown_claimed_at = None
        link.teardown_next_retry_at = None
        update_fields.extend(
            [
                "lifecycle_status",
                "status",
                "provision_phase",
                "provision_detail",
                "provision_claim_token",
                "provision_claimed_at",
                "provision_next_retry_at",
                "teardown_claim_token",
                "teardown_claimed_at",
                "teardown_next_retry_at",
            ]
        )
    link.save(update_fields=update_fields)
    transaction.on_commit(lambda: _queue_teardown_or_record_error(link.id))


def _compensate_late_session(
    link_id: int,
    session_uuid: uuid_lib.UUID,
    *,
    user: AbstractBaseUser,
) -> None:
    try:
        sl_client.request_json(
            "DELETE",
            f"/api/lens/sessions/{session_uuid}/",
            hfl_user=user,
        )
    except Exception as exc:
        if _source_lens_not_found(exc):
            return
        _record_late_source_lens_resource(
            link_id,
            field="sl_session_uuid",
            resource_uuid=session_uuid,
            error=f"Late session compensation failed: {exc}",
        )


def _compensate_late_assistant(
    link_id: int,
    assistant_uuid: uuid_lib.UUID,
) -> None:
    link = (
        LensSessionLink.objects.select_related("organization")
        .filter(pk=link_id)
        .first()
    )
    if link is None:
        return
    try:
        from apps.lens_bridge.services.assistants import _delete_sl_assistant

        _delete_sl_assistant(assistant_uuid)
        assistant_access.soft_delete_assistant_link(
            link.organization,
            assistant_uuid,
        )
    except Exception as exc:
        if _source_lens_not_found(exc):
            return
        _record_late_source_lens_resource(
            link_id,
            field="sl_assistant_uuid",
            resource_uuid=assistant_uuid,
            error=f"Late assistant compensation failed: {exc}",
        )


def _claim_copilot_chat_teardown(session_link_id: int) -> tuple[str | None, str]:
    now = timezone.now()
    with transaction.atomic():
        link = LensSessionLink.objects.select_for_update().filter(pk=session_link_id).first()
        if link is None:
            return None, "missing"
        if link.lifecycle_status == LensSessionLink.LifecycleStatus.DELETED:
            return None, "deleted"
        if link.lifecycle_status != LensSessionLink.LifecycleStatus.DELETING:
            return None, str(link.lifecycle_status)
        if (
            link.teardown_claimed_at
            and link.teardown_claimed_at
            > now - timedelta(seconds=TEARDOWN_CLAIM_TTL_SECONDS)
        ):
            return None, "busy"
        if link.teardown_next_retry_at and link.teardown_next_retry_at > now:
            return None, "scheduled"
        claim_token = uuid_lib.uuid4()
        link.lifecycle_status = LensSessionLink.LifecycleStatus.DELETING
        link.teardown_attempts += 1
        link.teardown_claim_token = claim_token
        link.teardown_claimed_at = now
        link.teardown_next_retry_at = next_retry_at(link.teardown_attempts)
        link.save(
            update_fields=[
                "teardown_attempts",
                "lifecycle_status",
                "teardown_claim_token",
                "teardown_claimed_at",
                "teardown_next_retry_at",
                "updated_at",
            ]
        )
    return str(claim_token), "claimed"


def _source_lens_not_found(exc: Exception) -> bool:
    return isinstance(exc, sl_client.LensBridgeError) and getattr(exc, "status_code", None) == 404


def _teardown_step(
    state: dict[str, Any],
    step: str,
    *,
    status: str,
    error: str = "",
) -> None:
    state[step] = {
        "status": status,
        "error": error[:1000],
        "updated_at": timezone.now().isoformat(),
    }


def _update_chat_claim(
    link: LensSessionLink,
    claim_token: str,
    *fields: str,
) -> None:
    """Persist intermediate Chat teardown state under the current lease."""

    values = {field: getattr(link, field) for field in fields}
    values["updated_at"] = timezone.now()
    updated = LensSessionLink.objects.filter(
        pk=link.id,
        teardown_claim_token=claim_token,
        lifecycle_status=LensSessionLink.LifecycleStatus.DELETING,
    ).update(**values)
    if updated != 1:
        raise ChatTeardownIncompleteError("Chat teardown lease was lost.")


def run_copilot_chat_teardown(*, session_link_id: int) -> dict[str, Any]:
    claim_token, claim_status = _claim_copilot_chat_teardown(session_link_id)
    if claim_token is None:
        return {"session_link_id": session_link_id, "status": claim_status}
    link = (
        LensSessionLink.objects.select_related(
            "knowledge_source",
            "knowledge_source__workspace_binding",
            "hfl_user",
            "organization",
            "chat_binding",
        )
        .filter(pk=session_link_id)
        .first()
    )
    if link is None:
        return {"session_link_id": session_link_id, "status": "missing"}

    org = link.organization
    user = link.hfl_user
    critical_errors: list[str] = []
    warnings: list[str] = []
    teardown_state = dict(link.teardown_state_json or {})

    if link.active_run_uuid:
        try:
            sl_client.request_json(
                "POST",
                f"/api/lens/runs/{link.active_run_uuid}/cancel/",
                hfl_user=user,
            )
        except Exception as exc:
            if not _source_lens_not_found(exc):
                warnings.append(f"cancel_run: {exc}")
                _teardown_step(teardown_state, "cancel_run", status="warning", error=str(exc))
            else:
                _teardown_step(teardown_state, "cancel_run", status="success")
        else:
            _teardown_step(teardown_state, "cancel_run", status="success")

    session_recovery_failed = False
    try:
        journal_session_uuid = _recover_journal_resource(
            link,
            _SESSION_CREATE_OPERATION,
            hfl_user=user,
        )
    except Exception as exc:
        journal_session_uuid = None
        session_recovery_failed = True
        critical_errors.append(f"recover_session_operation: {exc}")
    session_uuids = {
        item
        for item in (link.sl_session_uuid, journal_session_uuid)
        if item is not None
    }
    session_uuids.update(_late_remote_uuids(link, "session"))
    failed_session_uuids: list[uuid_lib.UUID] = []
    for session_uuid in sorted(session_uuids, key=str):
        try:
            sl_client.request_json(
                "DELETE",
                f"/api/lens/sessions/{session_uuid}/",
                hfl_user=user,
            )
        except Exception as exc:
            if not _source_lens_not_found(exc):
                failed_session_uuids.append(session_uuid)
                critical_errors.append(f"delete_session {session_uuid}: {exc}")
    link.sl_session_uuid = (
        failed_session_uuids[0] if failed_session_uuids else None
    )
    if journal_session_uuid and journal_session_uuid not in failed_session_uuids:
        _set_operation_status(
            link,
            _SESSION_CREATE_OPERATION,
            status="compensated",
        )
    _retain_failed_late_resources(
        link,
        "session",
        failed_session_uuids,
    )
    if failed_session_uuids or session_recovery_failed:
        detail = "; ".join(
            error
            for error in critical_errors
            if error.startswith(("delete_session ", "recover_session_operation:"))
        )
        _teardown_step(
            teardown_state,
            "delete_session",
            status="retry",
            error=detail,
        )
    else:
        _teardown_step(teardown_state, "delete_session", status="success")
    _update_chat_claim(
        link,
        claim_token,
        "sl_session_uuid",
        "provision_state_json",
    )

    session_cleanup_complete = not failed_session_uuids and not session_recovery_failed
    assistant_recovery_failed = False
    journal_assistant_uuid: uuid_lib.UUID | None = None
    failed_assistant_uuids: list[uuid_lib.UUID] = []
    ks = link.knowledge_source
    assistant_uuids: set[uuid_lib.UUID] = set()
    if session_cleanup_complete:
        try:
            journal_assistant_uuid = _recover_journal_resource(
                link,
                _ASSISTANT_CREATE_OPERATION,
            )
        except Exception as exc:
            assistant_recovery_failed = True
            critical_errors.append(f"recover_assistant_operation: {exc}")
        assistant_uuids = {
            item
            for item in (link.sl_assistant_uuid, journal_assistant_uuid)
            if item is not None
        }
        assistant_uuids.update(_late_remote_uuids(link, "assistant"))
        for assistant_uuid in sorted(assistant_uuids, key=str):
            try:
                from apps.lens_bridge.services.assistants import (
                    _delete_sl_assistant,
                )

                _delete_sl_assistant(assistant_uuid)
                assistant_access.soft_delete_assistant_link(org, assistant_uuid)
            except Exception as exc:
                failed_assistant_uuids.append(assistant_uuid)
                critical_errors.append(
                    f"delete_assistant {assistant_uuid}: {exc}"
                )
        link.sl_assistant_uuid = (
            failed_assistant_uuids[0] if failed_assistant_uuids else None
        )
        if (
            journal_assistant_uuid
            and journal_assistant_uuid not in failed_assistant_uuids
        ):
            _set_operation_status(
                link,
                _ASSISTANT_CREATE_OPERATION,
                status="compensated",
            )
        _retain_failed_late_resources(
            link,
            "assistant",
            failed_assistant_uuids,
        )
        if ks is not None:
            deleted_assistant_uuids = assistant_uuids.difference(
                failed_assistant_uuids
            )
            if ks.sl_assistant_uuid in deleted_assistant_uuids:
                LensKnowledgeSource.objects.filter(
                    pk=ks.id,
                    sl_assistant_uuid=ks.sl_assistant_uuid,
                ).update(sl_assistant_uuid=None, updated_at=timezone.now())
                ks.sl_assistant_uuid = None
        if failed_assistant_uuids or assistant_recovery_failed:
            detail = "; ".join(
                error
                for error in critical_errors
                if error.startswith(
                    ("delete_assistant ", "recover_assistant_operation:")
                )
            )
            _teardown_step(
                teardown_state,
                "delete_assistant",
                status="retry",
                error=detail,
            )
        else:
            _teardown_step(
                teardown_state,
                "delete_assistant",
                status="success",
            )
    else:
        _teardown_step(
            teardown_state,
            "delete_assistant",
            status="blocked",
            error="Session deletion must finish before Assistant deletion.",
        )
    _update_chat_claim(
        link,
        claim_token,
        "sl_assistant_uuid",
        "provision_state_json",
    )

    if (
        ks is not None
        and session_cleanup_complete
        and not failed_assistant_uuids
        and not assistant_recovery_failed
    ):
        try:
            from apps.lens_bridge.services.knowledge_source_teardown import (
                run_knowledge_source_teardown,
            )

            result = run_knowledge_source_teardown(
                knowledge_source_id=ks.id,
                owner_session_link_id=link.id,
            )
            if result.get("status") not in {"deleted"}:
                raise RuntimeError(
                    "Knowledge Source teardown is " + str(result.get("status"))
                )
            link.knowledge_source = None
            link.sl_assistant_uuid = None
            _update_chat_claim(
                link,
                claim_token,
                "knowledge_source",
                "sl_assistant_uuid",
                "provision_state_json",
            )
            _teardown_step(teardown_state, "delete_assistant", status="success")
            _teardown_step(teardown_state, "cleanup_workspace", status="success")
        except Exception as exc:
            critical_errors.append(f"cleanup_workspace: {exc}")
            _teardown_step(teardown_state, "cleanup_workspace", status="retry", error=str(exc))
    elif ks is None:
        _teardown_step(teardown_state, "cleanup_workspace", status="success")
    else:
        dependency = (
            "Session deletion must finish before workspace cleanup."
            if not session_cleanup_complete
            else "Assistant deletion must finish before workspace cleanup."
        )
        _teardown_step(
            teardown_state,
            "cleanup_workspace",
            status="blocked",
            error=dependency,
        )

    link.lifecycle_status = (
        LensSessionLink.LifecycleStatus.DELETING
        if critical_errors
        else LensSessionLink.LifecycleStatus.DELETED
    )
    link.status = LensSessionLink.Status.ARCHIVED
    link.provision_phase = (
        LensSessionLink.ProvisionPhase.CLEANING_UP
        if critical_errors
        else LensSessionLink.ProvisionPhase.DELETED
    )
    link.provision_detail = (
        "Chat cleanup is incomplete and will be retried."
        if critical_errors
        else "Chat resources deleted."
    )
    link.lifecycle_error = "; ".join([*critical_errors, *warnings])[:2000]
    link.active_run_uuid = None
    link.active_run_status = ""
    link.teardown_state_json = teardown_state
    link.teardown_claim_token = None
    link.teardown_claimed_at = None
    if not critical_errors:
        link.teardown_next_retry_at = None
    final_query = LensSessionLink.objects.filter(
        pk=link.id,
        teardown_claim_token=claim_token,
        lifecycle_status=LensSessionLink.LifecycleStatus.DELETING,
    )
    if not critical_errors:
        final_query = final_query.filter(
            sl_session_uuid__isnull=True,
            sl_assistant_uuid__isnull=True,
            knowledge_source__isnull=True,
        )
    updated = final_query.update(
        lifecycle_status=link.lifecycle_status,
        status=link.status,
        provision_phase=link.provision_phase,
        provision_detail=link.provision_detail,
        lifecycle_error=link.lifecycle_error,
        active_run_uuid=None,
        active_run_status="",
        teardown_state_json=teardown_state,
        teardown_claim_token=None,
        teardown_claimed_at=None,
        teardown_next_retry_at=link.teardown_next_retry_at,
        updated_at=timezone.now(),
    )
    if updated != 1:
        raise ChatTeardownIncompleteError("Chat teardown lease was lost.")
    if critical_errors:
        raise ChatTeardownIncompleteError("; ".join(critical_errors))
    return {
        "session_link_id": link.id,
        "status": "deleted",
        "warnings": warnings,
        "gateway_untouched": True,
    }


def _mark_provision_failed_by_id(
    session_link_id: int,
    claim_token: str,
    message: str,
) -> None:
    LensSessionLink.objects.filter(
        pk=session_link_id,
        lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
        provision_claim_token=claim_token,
    ).update(
        lifecycle_status=LensSessionLink.LifecycleStatus.FAILED,
        provision_phase=LensSessionLink.ProvisionPhase.QUEUED,
        provision_detail="Chat preparation failed.",
        lifecycle_error=(message or "provision failed")[:2000],
        provision_claim_token=None,
        provision_claimed_at=None,
        provision_next_retry_at=None,
        updated_at=timezone.now(),
    )


@transaction.atomic
def _transition_failed_provision_to_teardown(
    session_link_id: int,
    claim_token: str,
    *,
    message: str,
) -> bool:
    """Fence retry and hand incomplete compensation to durable teardown."""
    link = (
        LensSessionLink.objects.select_for_update()
        .filter(
            pk=session_link_id,
            lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
            provision_claim_token=claim_token,
        )
        .first()
    )
    if link is None:
        return False
    link.lifecycle_status = LensSessionLink.LifecycleStatus.DELETING
    link.status = LensSessionLink.Status.ARCHIVED
    link.provision_phase = LensSessionLink.ProvisionPhase.CLEANING_UP
    link.provision_detail = "Provisioning cleanup is incomplete and will be retried."
    link.lifecycle_error = message[:2000]
    link.provision_claim_token = None
    link.provision_claimed_at = None
    link.provision_next_retry_at = None
    link.teardown_attempts = 0
    link.teardown_claim_token = None
    link.teardown_claimed_at = None
    link.teardown_next_retry_at = None
    link.save(
        update_fields=[
            "lifecycle_status",
            "status",
            "provision_phase",
            "provision_detail",
            "lifecycle_error",
            "provision_claim_token",
            "provision_claimed_at",
            "provision_next_retry_at",
            "teardown_attempts",
            "teardown_claim_token",
            "teardown_claimed_at",
            "teardown_next_retry_at",
            "updated_at",
        ]
    )
    transaction.on_commit(lambda: _queue_teardown_or_record_error(link.id))
    return True


@transaction.atomic
def retry_copilot_chat_provision(link: LensSessionLink) -> LensSessionLink:
    locked = LensSessionLink.objects.select_for_update().get(pk=link.pk)
    if locked.lifecycle_status == LensSessionLink.LifecycleStatus.READY:
        return locked
    if locked.lifecycle_status == LensSessionLink.LifecycleStatus.PROVISIONING:
        claim_is_live = (
            locked.provision_claimed_at is not None
            and locked.provision_claimed_at
            > timezone.now() - timedelta(seconds=PROVISION_CLAIM_TTL_SECONDS)
        )
        if claim_is_live:
            return locked
    elif locked.lifecycle_status != LensSessionLink.LifecycleStatus.FAILED:
        raise ValidationError({"lifecycle_status": "Session is not retryable."})
    locked.lifecycle_status = LensSessionLink.LifecycleStatus.PROVISIONING
    locked.provision_phase = LensSessionLink.ProvisionPhase.QUEUED
    locked.provision_detail = "Chat creation is queued."
    locked.lifecycle_error = ""
    locked.provision_claim_token = None
    locked.provision_claimed_at = None
    locked.provision_next_retry_at = None
    locked.save(
        update_fields=[
            "lifecycle_status",
            "provision_phase",
            "provision_detail",
            "lifecycle_error",
            "provision_claim_token",
            "provision_claimed_at",
            "provision_next_retry_at",
            "updated_at",
        ]
    )
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
            provision_claim_token__isnull=True,
        ).update(
            provision_phase=LensSessionLink.ProvisionPhase.QUEUED,
            provision_detail=(
                "Chat preparation is waiting for the worker queue."
            ),
            lifecycle_error=str(exc)[:2000],
            provision_next_retry_at=timezone.now() + timedelta(seconds=60),
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


def _cleanup_failed_provision(
    link: LensSessionLink,
    claim_token: str,
) -> list[str]:
    """Best-effort compensation before a failed chat can be retried.

    The identifiers are retained when a remote deletion fails, allowing a
    retry to resume rather than create another orphaned SourceLens resource.
    """
    _set_phase(
        link,
        claim_token,
        LensSessionLink.ProvisionPhase.CLEANING_UP,
        "Cleaning up incomplete chat resources.",
    )
    link.refresh_from_db()
    errors: list[str] = []
    for kind in (_ASSISTANT_CREATE_OPERATION, _SESSION_CREATE_OPERATION):
        operation = dict((link.provision_state_json or {}).get(kind) or {})
        if (
            operation
            and not operation.get("remote_uuid")
            and operation.get("status") not in {"not_created", "compensated"}
        ):
            errors.append(f"{kind}: remote create outcome is unknown")
    journal_assistant_uuid = _operation_remote_uuid(
        link,
        _ASSISTANT_CREATE_OPERATION,
    )
    journal_session_uuid = _operation_remote_uuid(
        link,
        _SESSION_CREATE_OPERATION,
    )
    if journal_assistant_uuid and journal_assistant_uuid != link.sl_assistant_uuid:
        errors.append("assistant_create: journaled resource requires teardown")
    if journal_session_uuid and journal_session_uuid != link.sl_session_uuid:
        errors.append("session_create: journaled resource requires teardown")
    if _late_remote_uuids(link, "assistant") or _late_remote_uuids(link, "session"):
        errors.append("late_resources: durable teardown is required")
    if errors:
        _update_provision_claim(
            link,
            claim_token,
            "provision_state_json",
        )
        return errors
    session_cleanup_complete = True
    if link.sl_session_uuid:
        session_uuid = link.sl_session_uuid
        try:
            sl_client.request_json(
                "DELETE",
                f"/api/lens/sessions/{session_uuid}/",
                hfl_user=link.hfl_user,
            )
            link.sl_session_uuid = None
        except Exception as exc:
            if _source_lens_not_found(exc):
                link.sl_session_uuid = None
                if _operation_remote_uuid(link, _SESSION_CREATE_OPERATION) == session_uuid:
                    _set_operation_status(
                        link,
                        _SESSION_CREATE_OPERATION,
                        status="compensated",
                    )
            else:
                errors.append(f"delete_session: {exc}")
                session_cleanup_complete = False
        else:
            if _operation_remote_uuid(link, _SESSION_CREATE_OPERATION) == session_uuid:
                _set_operation_status(
                    link,
                    _SESSION_CREATE_OPERATION,
                    status="compensated",
                )
    assistant_cleanup_complete = session_cleanup_complete
    if session_cleanup_complete and link.sl_assistant_uuid:
        assistant_uuid = link.sl_assistant_uuid
        try:
            from apps.lens_bridge.services.assistants import _delete_sl_assistant

            _delete_sl_assistant(assistant_uuid)
            assistant_access.soft_delete_assistant_link(link.organization, assistant_uuid)
            link.sl_assistant_uuid = None
            if _operation_remote_uuid(link, _ASSISTANT_CREATE_OPERATION) == assistant_uuid:
                _set_operation_status(
                    link,
                    _ASSISTANT_CREATE_OPERATION,
                    status="compensated",
                )
            ks = link.knowledge_source
            if ks is not None and ks.sl_assistant_uuid == assistant_uuid:
                LensKnowledgeSource.objects.filter(
                    pk=ks.id,
                    sl_assistant_uuid=assistant_uuid,
                ).update(sl_assistant_uuid=None, updated_at=timezone.now())
                ks.sl_assistant_uuid = None
        except Exception as exc:
            errors.append(f"delete_assistant: {exc}")
            assistant_cleanup_complete = False
    if (
        link.knowledge_source_id
        and session_cleanup_complete
        and assistant_cleanup_complete
    ):
        try:
            ks = link.knowledge_source
            if ks is not None:
                from apps.lens_bridge.services.knowledge_source_teardown import (
                    run_knowledge_source_teardown,
                )

                result = run_knowledge_source_teardown(
                    knowledge_source_id=ks.id,
                    owner_session_link_id=link.id,
                )
                if result.get("status") != "deleted":
                    raise RuntimeError(
                        "Knowledge Source teardown is " + str(result.get("status"))
                    )
            link.knowledge_source = None
        except Exception as exc:
            errors.append(f"delete_knowledge_source: {exc}")
    _update_provision_claim(
        link,
        claim_token,
        "sl_session_uuid",
        "sl_assistant_uuid",
        "knowledge_source",
        "provision_state_json",
    )
    if errors:
        logger.warning("partial Copilot cleanup session_link_id=%s errors=%s", link.id, errors)
    return errors
