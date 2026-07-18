from __future__ import annotations

import logging
import ntpath
import posixpath
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.node.services.internal.agent_log import log_agent_dispatch, log_agent_outcome
from apps.node.services.interface import run_agent_task_sync
from apps.protection.models import (
    BackupConfig,
    BackupConfigDirectory,
    BackupPolicy,
    BackupSourceSnapshot,
    FileFilterRule,
)
from apps.protection.services.repository_compatibility import validate_backup_repository_compatible
from apps.restore.services.interface import create_restore_plan
from apps.source.constants import ResourceType
from apps.source.models import SourceResource
from apps.source.services.internal.nas_display import nfs_export_path
from apps.source.services.internal.nas_share_path import normalize_user_share_path
from apps.storage.repositories.models import Repository, RepositoryUsageShard
from apps.storage.services.internal.nas_repository import (
    mount_point_from_repo_status_result,
    nas_agent_repository_subdir,
    nas_repository_payload,
)
from apps.storage.services.internal.repository_errors import (
    REPOSITORY_ALREADY_EXISTS_CODE,
    REPOSITORY_ALREADY_EXISTS_MESSAGE,
    agent_result_has_repository_conflict,
)
from common.errors import AppError

COMPRESSION_LEVELS = {"none", "balanced", "high"}
CONFLICT_MODES = {"skip", "overwrite"}
SOURCE_TYPES = {"agent", "nas"}
PATH_TYPES = {"directory", "file", "unknown"}

logger = logging.getLogger(__name__)


def _advance_pipeline(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> None:
    """Advance the source pipeline step to 3 after config creation."""
    from apps.source.services.internal.source_pipeline import set_pipeline_steps

    prefix = "agent" if source_type == "agent" else "nas"
    source_key = f"{prefix}:{source_ref_id}"
    updated = set_pipeline_steps(
        organization_id=organization_id,
        ids=[source_key],
        step=3,
    )
    if source_key not in updated:
        raise ValidationError({"source_ref_id": "Backup source not found."})


def create_backup_config(
    *,
    organization_id: int,
    data: dict[str, Any],
) -> BackupConfig:
    payload = _config_payload(data, organization_id=organization_id)
    directories_data = payload.pop("directories", [])
    recovery_plans_data = payload.pop("recovery_plans", None)
    recovery_plan_enabled = payload.get("recovery_plan_enabled", False)

    if not directories_data:
        raise ValidationError({"directories": "At least one directory is required."})
    if recovery_plan_enabled and not recovery_plans_data:
        raise ValidationError({
            "recovery_plans": "At least one recovery plan is required when recovery_plan_enabled is true."
        })
    logger.info(
        "backup config create started org_id=%s source_type=%s source_ref_id=%s repository_id=%s name=%s dir_count=%s",
        organization_id,
        payload["source_type"],
        payload["source_ref_id"],
        payload["repository_id"],
        payload["name"],
        len(directories_data),
    )
    _initialize_direct_nas_repository_for_agent(
        organization_id=organization_id,
        source_type=payload["source_type"],
        source_ref_id=payload["source_ref_id"],
        repository_id=payload["repository_id"],
    )

    with transaction.atomic():
        config = BackupConfig.objects.create(organization_id=organization_id, **payload)

        dirs = []
        for idx, d in enumerate(directories_data):
            dirs.append(BackupConfigDirectory(
                organization_id=organization_id,
                backup_config=config,
                path=d["path"],
                path_type=d.get("path_type", BackupConfigDirectory.PathType.UNKNOWN),
                display_name=d.get("display_name", ""),
                estimated_size_bytes=d.get("estimated_size_bytes", 0),
                sort_order=idx,
            ))
        created_dirs = BackupConfigDirectory.objects.bulk_create(dirs)

        if recovery_plan_enabled and recovery_plans_data:
            for idx, rp in enumerate(recovery_plans_data):
                dir_id = rp.get("backup_config_dir_id")
                if dir_id is None:
                    matched = [
                        d for d in created_dirs
                        if _same_or_ancestor_path(d.path, rp["source_path"])
                    ]
                    dir_id = matched[0].id if matched else None
                if dir_id is None and rp.get("scope") != "snapshot":
                    raise ValidationError({"recovery_plans": "Recovery plan directory not found."})
                create_restore_plan(
                    organization_id=organization_id,
                    data={
                        "backup_config_id": config.id,
                        "backup_config_dir_id": dir_id,
                        "scope": rp.get("scope", "paths"),
                        "source_type": payload["source_type"],
                        "source_ref_id": payload["source_ref_id"],
                        "source_path": rp["source_path"],
                        "target_type": rp.get("target_type") or "agent",
                        "target_ref_id": rp.get("target_ref_id") or rp.get("restore_host_id"),
                        "restore_dir": rp["restore_dir"],
                        "conflict_mode": rp["conflict_mode"],
                        "enabled": True,
                        "sort_order": idx,
                    },
                )

        config.refresh_from_db()
        config_id = config.id
        source_type = payload["source_type"]
        source_ref_id = payload["source_ref_id"]
        _advance_pipeline(
            organization_id=organization_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
        )

    logger.info(
        "backup config create ok config_id=%s org_id=%s source_type=%s source_ref_id=%s repository_id=%s",
        config_id,
        organization_id,
        source_type,
        source_ref_id,
        payload["repository_id"],
    )
    _enqueue_direct_nas_usage_refresh(
        organization_id=organization_id,
        repository_ids=[payload["repository_id"]],
        trigger="protection.backup_config.create",
    )
    return BackupConfig.objects.get(pk=config_id)


def _config_payload(
    data: dict[str, Any],
    *,
    organization_id: int | None = None,
    current: BackupConfig | None = None,
) -> dict[str, Any]:
    effective_org_id = organization_id if organization_id is not None else (
        current.organization_id if current is not None else None
    )
    merged: dict[str, Any] = {}
    if current is not None:
        merged = {
            "name": current.name,
            "remark": current.remark,
            "source_type": current.source_type,
            "source_ref_id": current.source_ref_id,
            "repository_id": current.repository_id,
            "backup_policy_id": current.backup_policy_id,
            "file_filter_rule_id": current.file_filter_rule_id,
            "compression_level": current.compression_level,
            "recovery_plan_enabled": current.recovery_plan_enabled,
        }
    merged.update(data)

    name = str(merged.get("name") or "").strip()
    if not name:
        raise ValidationError({"name": "Name is required."})

    source_type = str(merged.get("source_type") or "").strip().lower()
    if source_type not in SOURCE_TYPES:
        raise ValidationError({"source_type": f"Must be one of: {', '.join(sorted(SOURCE_TYPES))}."})

    source_ref_id = _int(merged, "source_ref_id")
    if source_ref_id <= 0:
        raise ValidationError({"source_ref_id": "Must be a positive integer."})

    repository_id = _int(merged, "repository_id")
    if repository_id <= 0:
        raise ValidationError({"repository_id": "Must be a positive integer."})

    backup_policy_id = _optional_int(merged, "backup_policy_id")
    file_filter_rule_id = _optional_int(merged, "file_filter_rule_id")

    if effective_org_id is not None:
        _validate_source_exists(
            organization_id=effective_org_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
        )
        _validate_repository_exists(
            organization_id=effective_org_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
            repository_id=repository_id,
        )
        _validate_unique_source_config(
            organization_id=effective_org_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
            current_config_id=current.id if current is not None else None,
        )
        if backup_policy_id is not None:
            _validate_backup_policy_exists(
                organization_id=effective_org_id,
                policy_id=backup_policy_id,
            )
        if file_filter_rule_id is not None:
            _validate_file_filter_rule_exists(
                organization_id=effective_org_id,
                rule_id=file_filter_rule_id,
            )

    raw_compression = merged.get("compression_level", BackupConfig.CompressionLevel.BALANCED)
    if not isinstance(raw_compression, str) or not raw_compression.strip():
        raise ValidationError(
            {"compression_level": "Must be one of: balanced, high, none."}
        )
    compression = raw_compression.strip().lower()
    if compression not in COMPRESSION_LEVELS:
        raise ValidationError(
            {"compression_level": "Must be one of: balanced, high, none."}
        )

    recovery_plan_enabled = bool(merged.get("recovery_plan_enabled", False))

    result = {
        "name": name,
        "remark": str(merged.get("remark") or "").strip(),
        "source_type": source_type,
        "source_ref_id": source_ref_id,
        "repository_id": repository_id,
        "backup_policy_id": backup_policy_id,
        "file_filter_rule_id": file_filter_rule_id,
        "compression_level": compression,
        "recovery_plan_enabled": recovery_plan_enabled,
    }

    # Pass through directories and recovery_plans for creation
    directories: list[dict[str, Any]] | None = None
    if "directories" in data:
        directories = _validate_directories(data["directories"])
        if source_type == "nas" and effective_org_id is not None and directories:
            directories = _normalize_nas_directory_paths(
                organization_id=effective_org_id,
                source_ref_id=source_ref_id,
                directories=directories,
            )
        result["directories"] = directories
    if "recovery_plans" in data:
        result["recovery_plans"] = _validate_recovery_plans(
            data["recovery_plans"],
            organization_id=effective_org_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
            directories=directories or [],
        )

    return result


def _validate_source_exists(*, organization_id: int, source_type: str, source_ref_id: int) -> None:
    if source_type == "agent":
        exists = Node.objects.filter(
            organization_id=organization_id,
            role=NodeRole.AGENT,
            id=source_ref_id,
            is_deleted=False,
        ).exists()
    else:
        exists = SourceResource.objects.filter(
            organization_id=organization_id,
            resource_type=ResourceType.NAS,
            id=source_ref_id,
            is_deleted=False,
        ).exists()
    if not exists:
        raise ValidationError({"source_ref_id": "Backup source not found."})


def _validate_repository_exists(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
    repository_id: int,
) -> None:
    validate_backup_repository_compatible(
        organization_id=organization_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
        repository_id=repository_id,
    )


def _validate_unique_source_config(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
    current_config_id: int | None = None,
) -> None:
    queryset = BackupConfig.objects.filter(
        organization_id=organization_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
    )
    if current_config_id is not None:
        queryset = queryset.exclude(id=current_config_id)
    if queryset.exists():
        raise ValidationError({"source_ref_id": "Backup source already has a backup configuration."})


def _initialize_direct_nas_repository_for_agent(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
    repository_id: int,
) -> None:
    if source_type != "agent":
        return
    repository = Repository.objects.filter(
        organization_id=organization_id,
        id=repository_id,
        repo_type=Repository.Type.NAS,
        bind_node_id__isnull=True,
    ).filter(
        Q(bind_node_type__isnull=True) | Q(bind_node_type="")
    ).exclude(status=Repository.Status.REMOVED).first()
    if repository is None:
        return
    node = Node.objects.filter(
        organization_id=organization_id,
        role=NodeRole.AGENT,
        id=source_ref_id,
        status=Node.Status.ONLINE,
        is_deleted=False,
    ).first()
    if node is None:
        raise ValidationError({"source_ref_id": "Agent source is offline."})
    payload = nas_repository_payload(
        repository=repository,
        subdir=nas_agent_repository_subdir(node.id),
        node_id=node.id,
    )
    repository_subdir = str(payload["subdir"])
    previously_initialized = RepositoryUsageShard.objects.filter(
        organization_id=organization_id,
        repository_id=repository.id,
        usage_scope=RepositoryUsageShard.Scope.DIRECT_NAS_AGENT,
        node_id=node.id,
        repository_subdir=repository_subdir,
        last_success_checked_at__isnull=False,
    ).exists()
    task_kind = "repo.status" if previously_initialized else "repo.initialize"
    correlation_id = f"{source_type}:{source_ref_id}:{repository_id}"
    log_agent_dispatch(
        "backup_config nas repo init",
        node_id=node.id,
        kind=task_kind,
        correlation_type="protection.backup_config",
        correlation_id=correlation_id,
        repository_id=repository_id,
    )
    outcome = run_agent_task_sync(
        organization_id=organization_id,
        node_id=node.id,
        kind=task_kind,
        payload={"repository": payload},
        correlation_type="protection.backup_config",
        correlation_id=correlation_id,
        wait_timeout_seconds=180,
    )
    log_agent_outcome(
        "backup_config nas repo init",
        outcome=outcome,
        node_id=node.id,
        kind=task_kind,
        correlation_type="protection.backup_config",
        correlation_id=correlation_id,
        repository_id=repository_id,
    )
    if outcome.task.status != "success":
        if agent_result_has_repository_conflict(outcome.result):
            raise AppError(
                code=REPOSITORY_ALREADY_EXISTS_CODE,
                status=409,
                retryable=False,
                title="Repository already exists",
                diagnostic=REPOSITORY_ALREADY_EXISTS_MESSAGE,
                meta={"repository_type": repository.repo_type},
            )
        message = str(getattr(outcome.task, "last_error", "") or "").strip()
        if not message and isinstance(outcome.result, dict):
            message = str(outcome.result.get("error") or outcome.result.get("stderr") or "").strip()
        raise ValidationError({
            "repository_id": _sanitize_repository_error(
                message or "NAS repository initialization failed.",
                repository.config,
            )
        })
    checked_at = timezone.now()
    shard_defaults = {
        "is_active": True,
        "status": RepositoryUsageShard.Status.SUCCESS,
        "last_error": "",
        "last_checked_at": checked_at,
        "last_success_checked_at": checked_at,
    }
    mount_point = mount_point_from_repo_status_result(outcome.result)
    if mount_point:
        shard_defaults["mount_point"] = mount_point
    RepositoryUsageShard.objects.update_or_create(
        organization_id=organization_id,
        repository_id=repository.id,
        usage_scope=RepositoryUsageShard.Scope.DIRECT_NAS_AGENT,
        node_id=node.id,
        repository_subdir=repository_subdir,
        defaults=shard_defaults,
    )
    if repository.health != Repository.Health.ONLINE:
        repository.health = Repository.Health.ONLINE
        repository.last_checked_at = checked_at
        repository.save(update_fields=["health", "last_checked_at", "updated_at"])


def _should_initialize_direct_nas_repository(
    *,
    current: BackupConfig | None,
    payload: dict[str, Any],
) -> bool:
    if current is None:
        return True
    return any(
        payload.get(field) != getattr(current, field)
        for field in ("source_type", "source_ref_id", "repository_id")
    )


def _enqueue_direct_nas_usage_refresh(
    *,
    organization_id: int,
    repository_ids: list[int],
    trigger: str,
) -> None:
    direct_nas_ids = list(
        Repository.objects.filter(
            organization_id=organization_id,
            id__in=repository_ids,
            repo_type=Repository.Type.NAS,
            bind_node_id__isnull=True,
        )
        .filter(Q(bind_node_type__isnull=True) | Q(bind_node_type=""))
        .exclude(status=Repository.Status.REMOVED)
        .values_list("id", flat=True)
    )
    if not direct_nas_ids:
        return
    try:
        from apps.storage.services.internal.repository_usage import enqueue_repository_usage_refresh

        enqueue_repository_usage_refresh(
            organization_id=organization_id,
            repository_ids=direct_nas_ids,
            force=True,
            trigger=trigger,
        )
    except Exception:
        logger.exception(
            "failed to enqueue direct NAS repository usage refresh org_id=%s repository_ids=%s trigger=%s",
            organization_id,
            direct_nas_ids,
            trigger,
        )


def _sanitize_repository_error(message: str, config: dict | None) -> str:
    sanitized = str(message or "")
    if not isinstance(config, dict):
        return sanitized
    for key, value in config.items():
        text = str(value or "")
        if not text:
            continue
        key_text = str(key).lower()
        if "password" in key_text or "secret" in key_text or len(text) >= 6:
            sanitized = sanitized.replace(text, "***")
    return sanitized


def _validate_backup_policy_exists(*, organization_id: int, policy_id: int) -> None:
    if not BackupPolicy.objects.filter(organization_id=organization_id, id=policy_id).exists():
        raise ValidationError({"backup_policy_id": "Backup policy not found."})


def _validate_file_filter_rule_exists(*, organization_id: int, rule_id: int) -> None:
    if not FileFilterRule.objects.filter(organization_id=organization_id, id=rule_id).exists():
        raise ValidationError({"file_filter_rule_id": "File filter rule not found."})


def _validate_restore_host_exists(*, organization_id: int | None, restore_host_id: int | None) -> None:
    if organization_id is None or restore_host_id is None:
        return
    exists = Node.objects.filter(
        organization_id=organization_id,
        role=NodeRole.AGENT,
        id=restore_host_id,
        is_deleted=False,
    ).exists()
    if not exists:
        raise ValidationError({"restore_host_id": "Restore host not found."})


def _validate_restore_target_exists(
    *,
    organization_id: int | None,
    target_type: str,
    target_ref_id: int | None,
) -> None:
    if target_ref_id is None:
        raise ValidationError({"target_ref_id": "Restore target is required."})
    if organization_id is None:
        return
    if target_type == "agent":
        exists = Node.objects.filter(
            organization_id=organization_id,
            role=NodeRole.AGENT,
            id=target_ref_id,
            is_deleted=False,
        ).exists()
    elif target_type == "nas":
        exists = SourceResource.objects.filter(
            organization_id=organization_id,
            resource_type=ResourceType.NAS,
            id=target_ref_id,
            is_deleted=False,
        ).exists()
    else:
        raise ValidationError({"target_type": "Must be one of: agent, nas."})
    if not exists:
        raise ValidationError({"target_ref_id": "Restore target not found."})


def _normalize_nas_directory_paths(
    *,
    organization_id: int,
    source_ref_id: int,
    directories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resource = (
        SourceResource.objects.filter(
            organization_id=organization_id,
            id=source_ref_id,
            resource_type=ResourceType.NAS,
            is_deleted=False,
        )
        .first()
    )
    if resource is None:
        return directories
    mount_root = _clean_dir_path(resource.effective_mount_point())
    if not mount_root:
        return directories
    config = resource.config if isinstance(resource.config, dict) else {}
    export_path = nfs_export_path(resource_type=resource.resource_type, config=config)
    normalized: list[dict[str, Any]] = []
    for item in directories:
        row = dict(item)
        row["path"] = normalize_user_share_path(
            mount_root=mount_root,
            export_path=export_path,
            user_path=str(row.get("path") or ""),
        )
        normalized.append(row)
    return normalized


def _validate_directories(directories: Any) -> list[dict[str, Any]]:
    if not isinstance(directories, list) or len(directories) == 0:
        raise ValidationError({"directories": "At least one source path is required."})
    seen_paths: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in directories:
        if not isinstance(item, dict):
            raise ValidationError({"directories": "Each source path must be an object."})
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            raise ValidationError({"directories": "Source path is required."})
        path = _clean_dir_path(raw_path)
        if not _is_absolute_source_path(path):
            raise ValidationError({"directories": f"Source path must be absolute: {path}."})
        path_type = str(item.get("path_type") or "unknown").strip().lower()
        if path_type not in PATH_TYPES:
            path_type = "unknown"
        if path in seen_paths:
            raise ValidationError({"directories": f"Duplicate source path: {path}."})
        for existing in seen_paths:
            if _same_or_ancestor_path(existing, path) or _same_or_ancestor_path(path, existing):
                raise ValidationError({"directories": f"Parent/child source path conflict: {path}."})
        seen_paths.add(path)
        result.append({
            "path": path,
            "path_type": path_type,
            "display_name": str(item.get("display_name") or "").strip(),
            "estimated_size_bytes": _int(item, "estimated_size_bytes"),
        })
    return result


def _validate_recovery_plans(
    recovery_plans: Any,
    *,
    organization_id: int | None,
    source_type: str,
    source_ref_id: int,
    directories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if recovery_plans in (None, ""):
        return []
    if not isinstance(recovery_plans, list):
        raise ValidationError({"recovery_plans": "recovery_plans must be a list."})

    configured_paths = [item["path"] for item in directories if item.get("path")]
    result: list[dict[str, Any]] = []
    for item in recovery_plans:
        if not isinstance(item, dict):
            raise ValidationError({"recovery_plans": "Each recovery plan must be an object."})
        scope = str(item.get("scope") or "paths").strip().lower()
        if scope not in {"snapshot", "paths"}:
            raise ValidationError({"scope": "Must be one of: paths, snapshot."})
        raw_source_path = str(item.get("source_path") or "").strip()
        raw_restore_dir = str(item.get("restore_dir") or "").strip()
        if not raw_restore_dir:
            raise ValidationError({"restore_dir": "Restore directory is required."})
        restore_dir = _clean_dir_path(raw_restore_dir)
        conflict_mode = str(item.get("conflict_mode") or "").strip().lower()
        if conflict_mode not in CONFLICT_MODES:
            raise ValidationError({"conflict_mode": f"Must be one of: {', '.join(sorted(CONFLICT_MODES))}."})
        target_type = str(item.get("target_type") or "agent").strip().lower()
        target_ref_id = _optional_int(item, "target_ref_id")
        restore_host_id = _optional_int(item, "restore_host_id")
        if target_ref_id is None:
            target_ref_id = restore_host_id
        if restore_host_id is None and target_type == "agent":
            restore_host_id = target_ref_id
        _validate_restore_target_exists(
            organization_id=organization_id,
            target_type=target_type,
            target_ref_id=target_ref_id,
        )
        source_paths = [""] if scope == "snapshot" else [_clean_dir_path(raw_source_path)] if raw_source_path else configured_paths
        if not source_paths:
            raise ValidationError({"source_path": "Source path is required."})
        for source_path in source_paths:
            if scope != "snapshot" and not _is_absolute_source_path(source_path):
                raise ValidationError({"source_path": "Recovery source path must be absolute."})
            if scope != "snapshot" and configured_paths and not any(_same_or_ancestor_path(path, source_path) for path in configured_paths):
                raise ValidationError({"source_path": f"Recovery source path is outside configured directories: {source_path}."})
            result.append({
                "scope": scope,
                "source_type": source_type,
                "source_ref_id": source_ref_id,
                "source_path": source_path,
                "backup_config_dir_id": None if scope == "snapshot" else _optional_int(item, "backup_config_dir_id"),
                "target_type": target_type,
                "target_ref_id": target_ref_id,
                "restore_host_id": restore_host_id,
                "restore_dir": restore_dir,
                "conflict_mode": conflict_mode,
            })
    return result


def _is_windows_path(path: str) -> bool:
    return "\\" in path or (len(path) >= 2 and path[1] == ":")


def _clean_dir_path(path: str) -> str:
    if _is_windows_path(path):
        return ntpath.normpath(path)
    return posixpath.normpath(path)


def _same_or_ancestor_path(ancestor_path: str, child_path: str) -> bool:
    if _is_windows_path(ancestor_path) or _is_windows_path(child_path):
        ancestor = ntpath.normcase(_clean_dir_path(ancestor_path).rstrip("\\/"))
        child = ntpath.normcase(_clean_dir_path(child_path).rstrip("\\/"))
        return child == ancestor or child.startswith(ancestor + "\\")
    ancestor = _clean_dir_path(ancestor_path).rstrip("/") or "/"
    child = _clean_dir_path(child_path).rstrip("/") or "/"
    return child == ancestor or child.startswith(ancestor + "/")


def _int(data: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(data.get(key, default) or default)
    except (TypeError, ValueError) as exc:
        raise ValidationError({key: f"{key} must be an integer."}) from exc


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    raw = data.get(key)
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({key: f"{key} must be an integer."}) from exc
    if value <= 0:
        raise ValidationError({key: "Must be a positive integer."})
    return value


def delete_backup_config(*, config: BackupConfig) -> dict[str, Any]:
    raise ValidationError({
        "detail": "Backup config deletion is not supported. Clean up the source endpoint instead."
    })


def purge_backup_config_data_for_source(
    *,
    organization_id: int,
    source_type: str,
    source_ref_id: int,
) -> dict[str, int]:
    """Internal source cleanup path for removing backup artifacts tied to a source."""
    from apps.restore.models import RestorePlan

    configs = list(
        BackupConfig.objects.filter(
            organization_id=organization_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
        ).values_list("id", "repository_id")
    )
    config_ids = [row[0] for row in configs]
    if not config_ids:
        return {"backup_configs_removed": 0, "snapshots_removed": 0, "restore_plans_removed": 0}
    repository_ids = sorted({int(row[1]) for row in configs})

    snapshots_removed = BackupSourceSnapshot.objects.filter(
        organization_id=organization_id,
        backup_config_id__in=config_ids,
    ).delete()[0]
    restore_plans_removed = RestorePlan.objects.filter(
        organization_id=organization_id,
        backup_config_id__in=config_ids,
    ).delete()[0]
    backup_configs_removed = BackupConfig.objects.filter(id__in=config_ids).delete()[0]
    _enqueue_direct_nas_usage_refresh(
        organization_id=organization_id,
        repository_ids=repository_ids,
        trigger="protection.backup_config.purge",
    )
    return {
        "backup_configs_removed": backup_configs_removed,
        "snapshots_removed": snapshots_removed,
        "restore_plans_removed": restore_plans_removed,
    }


def _sync_backup_config_directories(
    *,
    config: BackupConfig,
    directories_data: list[dict[str, Any]],
) -> None:
    if not directories_data:
        raise ValidationError({"directories": "At least one directory is required."})

    existing_by_path = {
        directory.path: directory
        for directory in BackupConfigDirectory.objects.filter(backup_config=config)
    }
    next_by_path = {directory["path"]: directory for directory in directories_data}

    created_or_updated: list[BackupConfigDirectory] = []
    for idx, directory_data in enumerate(directories_data):
        path = directory_data["path"]
        directory = existing_by_path.get(path)
        if directory is None:
            directory = BackupConfigDirectory(
                organization_id=config.organization_id,
                backup_config=config,
                path=path,
            )
        directory.path_type = directory_data.get("path_type", BackupConfigDirectory.PathType.UNKNOWN)
        directory.display_name = directory_data.get("display_name", "")
        directory.estimated_size_bytes = directory_data.get("estimated_size_bytes", 0)
        directory.sort_order = idx
        directory.save()
        created_or_updated.append(directory)

    from apps.restore.models import RestorePlan

    for plan in RestorePlan.objects.filter(
        organization_id=config.organization_id,
        backup_config_id=config.id,
    ):
        if plan.scope == RestorePlan.Scope.SNAPSHOT:
            continue
        if not _is_absolute_source_path(plan.source_path):
            raise ValidationError({
                "directories": (
                    "Existing recovery plan source path must be absolute: "
                    f"{plan.source_path}."
                )
            })
        matched = [
            directory
            for directory in created_or_updated
            if _same_or_ancestor_path(directory.path, plan.source_path)
        ]
        if not matched:
            raise ValidationError({
                "directories": (
                    "Existing recovery plan source path is outside configured directories: "
                    f"{plan.source_path}."
                )
            })
        matched.sort(key=lambda directory: len(directory.path), reverse=True)
        directory = matched[0]
        if plan.backup_config_dir_id != directory.id:
            plan.backup_config_dir_id = directory.id
            plan.save(update_fields=["backup_config_dir_id", "updated_at"])

    removed_paths = set(existing_by_path) - set(next_by_path)
    if removed_paths:
        BackupConfigDirectory.objects.filter(
            backup_config=config,
            path__in=removed_paths,
        ).delete()


def update_backup_config(
    *,
    config: BackupConfig,
    data: dict[str, Any],
) -> BackupConfig:
    previous_repository_id = config.repository_id
    previous_source_type = config.source_type
    previous_source_ref_id = config.source_ref_id
    payload = _config_payload(data, current=config)
    directories_data = payload.pop("directories", None)
    payload.pop("recovery_plans", None)
    logger.info(
        "backup config update started config_id=%s org_id=%s fields=%s",
        config.id,
        config.organization_id,
        sorted(data.keys()),
    )
    if _should_initialize_direct_nas_repository(current=config, payload=payload):
        _initialize_direct_nas_repository_for_agent(
            organization_id=config.organization_id,
            source_type=payload["source_type"],
            source_ref_id=payload["source_ref_id"],
            repository_id=payload["repository_id"],
        )
    for field in ("name", "remark", "source_type", "source_ref_id", "repository_id",
                  "backup_policy_id", "file_filter_rule_id", "compression_level",
                  "recovery_plan_enabled"):
        if field in payload:
            setattr(config, field, payload[field])
    with transaction.atomic():
        config.save()
        if directories_data is not None:
            _sync_backup_config_directories(
                config=config,
                directories_data=directories_data,
            )
        config.refresh_from_db()
    logger.info(
        "backup config update ok config_id=%s org_id=%s repository_id=%s",
        config.id,
        config.organization_id,
        config.repository_id,
    )
    if any(
        (
            previous_repository_id != config.repository_id,
            previous_source_type != config.source_type,
            previous_source_ref_id != config.source_ref_id,
        )
    ):
        _enqueue_direct_nas_usage_refresh(
            organization_id=config.organization_id,
            repository_ids=[previous_repository_id, config.repository_id],
            trigger="protection.backup_config.update",
        )
    return config


def _is_absolute_source_path(path: str) -> bool:
    clean_path = str(path or "").strip()
    if not clean_path:
        return False
    if _is_windows_path(clean_path):
        return ntpath.isabs(clean_path)
    return posixpath.isabs(clean_path)


__all__ = [
    "create_backup_config",
    "delete_backup_config",
    "purge_backup_config_data_for_source",
    "update_backup_config",
]
