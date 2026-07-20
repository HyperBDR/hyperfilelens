from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.apps import apps
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.storage.repositories.models import Repository, RepositoryUsageShard
from apps.storage.services.internal.kopia_cli import (
    KopiaCliError,
    connect_s3_repository,
    content_stats as kopia_content_stats,
)

logger = logging.getLogger(__name__)

_GB = 1024**3
_KOPIA_ESTIMATED_USAGE_FACTOR = 1.05
_USAGE_REFRESH_DEDUP_TTL_SECONDS = 60
_DEFAULT_STALE_AFTER_SECONDS = 900
_SIZE_RE = re.compile(
    r"(?P<key>total\s*packed|packed|total\s*size|total\s*bytes|size|used|total)\s*[:=]\s*(?P<num>[\d.,]+)\s*(?P<unit>[KMGT]?B)?",
    re.IGNORECASE,
)
_KOPIA_PHYSICAL_SIZE_KEYS = (
    "totalCompressedSize",
    "total_compressed_size",
    "compressedSize",
    "compressed_size",
    "totalPackedSize",
    "total_packed_size",
    "packedSize",
    "packed_size",
    "storedSize",
    "stored_size",
    "repositorySize",
    "repository_size",
    "contentSize",
    "content_size",
)
_KOPIA_LOGICAL_SIZE_KEYS = (
    "totalSize",
    "total_size",
    "totalLogicalSize",
    "total_logical_size",
    "size",
)


@dataclass(frozen=True)
class RepositoryUsageProbeResult:
    estimated_usage_bytes: int | None
    capacity_bytes: int | None
    error: str = ""
    mount_point: str = ""


def capacity_bytes_from_config(config: dict | None) -> int:
    if not isinstance(config, dict):
        return 0
    try:
        quota_gb = float(config.get("quota_gb") or 0)
    except (TypeError, ValueError):
        return 0
    if quota_gb <= 0:
        return 0
    return int(quota_gb * _GB)


def apply_capacity_from_config(repository: Repository) -> bool:
    capacity = capacity_bytes_from_config(repository.config)
    if capacity <= 0:
        return False
    if repository.capacity_bytes == capacity:
        return False
    repository.capacity_bytes = capacity
    return True


def _parse_size_value(num: str, unit: str) -> int:
    try:
        value = float(str(num).replace(",", ""))
    except ValueError:
        return 0
    unit = (unit or "B").upper()
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
    }
    return int(value * multipliers.get(unit, 1))


def parse_kopia_content_stats(stdout: str) -> int:
    text = (stdout or "").strip()
    if not text:
        return 0
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        for key in (*_KOPIA_PHYSICAL_SIZE_KEYS, *_KOPIA_LOGICAL_SIZE_KEYS):
            value = payload.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                return int(value)
        stats = payload.get("stats")
        if isinstance(stats, dict):
            nested = parse_kopia_content_stats(json.dumps(stats))
            if nested >= 0:
                return nested

    best = 0
    packed_best = 0
    for match in _SIZE_RE.finditer(text):
        key = (match.group("key") or "").lower().replace(" ", "")
        if "packed" in key:
            packed_best = max(packed_best, _parse_size_value(match.group("num"), match.group("unit") or "B"))
            continue
        if "total" not in key and key != "size":
            continue
        parsed = _parse_size_value(match.group("num"), match.group("unit") or "B")
        best = max(best, parsed)
    return packed_best or best


def kopia_estimated_usage_from_packed(packed_bytes: int) -> int:
    return max(0, int(packed_bytes * _KOPIA_ESTIMATED_USAGE_FACTOR))


def kopia_repository_estimated_usage_bytes(repository: Repository) -> int | None:
    if repository.repo_type != Repository.Type.S3:
        return None
    if repository.status != Repository.Status.CREATED:
        return None
    try:
        connect_s3_repository(repository)
        result = kopia_content_stats(repository)
        packed = parse_kopia_content_stats(result.stdout)
        if packed <= 0:
            return None
        return kopia_estimated_usage_from_packed(packed)
    except KopiaCliError as exc:
        logger.info("kopia content stats unavailable for repository %s: %s", repository.id, exc)
        return None


def agent_path_usage_bytes(
    *,
    organization_id: int,
    node_id: int,
    path: str,
) -> tuple[int, int] | None:
    from apps.node.models import Node
    from apps.node.services.internal.agent_log import log_agent_dispatch, log_agent_exception, log_agent_outcome
    from apps.node.services.interface import run_agent_task_sync

    clean_path = str(path or "").strip()
    if not clean_path:
        return None
    node = Node.objects.filter(
        id=node_id,
        organization_id=organization_id,
        status=Node.Status.ONLINE,
    ).first()
    if node is None:
        logger.info("path.usage skipped node offline node_id=%s path=%s", node_id, clean_path)
        return None
    log_agent_dispatch(
        "storage path usage",
        node_id=node.id,
        kind="path.usage",
        correlation_type="storage_repository",
        correlation_id=str(node_id),
        path=clean_path,
    )
    try:
        outcome = run_agent_task_sync(
            organization_id=organization_id,
            node_id=node.id,
            kind="path.usage",
            payload={"path": clean_path},
            correlation_type="storage_repository",
            correlation_id=str(node_id),
            wait_timeout_seconds=90,
        )
    except Exception as exc:
        log_agent_exception(
            "storage path usage",
            node_id=node.id,
            kind="path.usage",
            exc=exc,
            correlation_type="storage_repository",
            correlation_id=str(node_id),
            path=clean_path,
        )
        return None
    log_agent_outcome(
        "storage path usage",
        outcome=outcome,
        node_id=node.id,
        kind="path.usage",
        correlation_type="storage_repository",
        correlation_id=str(node_id),
        path=clean_path,
    )
    if outcome.task.status != "success":
        return None
    result = outcome.result if isinstance(outcome.result, dict) else {}
    used = int(result.get("used_bytes") or 0)
    total = int(result.get("total_bytes") or 0)
    if used <= 0 and total <= 0:
        return None
    return max(0, used), max(0, total)


def _agent_repository_payload(repository: Repository) -> tuple[int, dict[str, Any]] | None:
    from apps.storage.services.internal.nas_repository import (
        nas_proxy_repository_subdir,
        nas_repository_payload,
        validate_proxy_for_repository,
    )
    from apps.storage.services.internal.proxy_fs_repository import (
        proxy_fs_repository_payload,
        validate_proxy_for_proxy_fs,
    )

    if repository.repo_type == Repository.Type.PROXY_FS:
        try:
            node = validate_proxy_for_proxy_fs(repository)
        except ValidationError:
            return None
        return node.id, {"repository": proxy_fs_repository_payload(repository)}

    if repository.repo_type == Repository.Type.NAS:
        try:
            node = validate_proxy_for_repository(repository)
        except ValidationError:
            return None
        return node.id, {
            "repository": nas_repository_payload(
                repository=repository,
                subdir=nas_proxy_repository_subdir(repository),
                node_id=node.id,
            )
        }
    return None


def _strip_repository_subdir(path: str, repository_subdir: str = "") -> str:
    clean_path = str(path or "").strip().rstrip("/")
    subdir = str(repository_subdir or "").strip().strip("/")
    if not clean_path or not subdir:
        return clean_path
    normalized_path = clean_path.replace("\\", "/")
    suffix = f"/{subdir}"
    if normalized_path == subdir:
        return ""
    if normalized_path.endswith(suffix):
        return clean_path[: -len(suffix)].rstrip("/")
    return clean_path


def _repo_status_mount_point(result: dict[str, Any], *, repository_subdir: str = "") -> str:
    candidates: list[Any] = [
        result.get("mount_point"),
        result.get("resolved_mount_point"),
    ]
    repository = result.get("repository")
    if isinstance(repository, dict):
        candidates.extend([repository.get("mount_point"), repository.get("resolved_mount_point")])
        nas = repository.get("nas")
        if isinstance(nas, dict):
            candidates.extend([nas.get("mount_point"), nas.get("resolved_mount_point")])
    nas = result.get("nas")
    if isinstance(nas, dict):
        candidates.extend([nas.get("mount_point"), nas.get("resolved_mount_point")])

    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value.rstrip("/")

    for key in ("repository_path", "path"):
        value = str(result.get(key) or "").strip()
        stripped = _strip_repository_subdir(value, repository_subdir)
        if stripped:
            return stripped

    space = result.get("space_info")
    if isinstance(space, dict):
        stripped = _strip_repository_subdir(str(space.get("path") or ""), repository_subdir)
        if stripped:
            return stripped
    return ""


def _parse_agent_repo_status_result(
    result: dict[str, Any],
    *,
    repository_subdir: str = "",
) -> tuple[int | None, int | None, str]:
    estimated: int | None = None
    raw_estimated = result.get("estimated_usage_bytes")
    if raw_estimated is not None:
        try:
            estimated = max(0, int(raw_estimated))
        except (TypeError, ValueError):
            estimated = None
    if estimated is None:
        content_stats = result.get("content_stats")
        stdout = ""
        if isinstance(content_stats, dict):
            stdout = str(content_stats.get("stdout") or "")
        if not stdout:
            stdout = str(result.get("stdout") or "")
        packed = parse_kopia_content_stats(stdout)
        if packed > 0:
            estimated = kopia_estimated_usage_from_packed(packed)

    fs_total: int | None = None
    fs_used: int | None = None
    space = result.get("space_info")
    if isinstance(space, dict):
        try:
            total = int(space.get("total_bytes") or 0)
            if total > 0:
                fs_total = total
        except (TypeError, ValueError):
            fs_total = None
        try:
            used = int(space.get("used_bytes") or 0)
            if used >= 0:
                fs_used = used
        except (TypeError, ValueError):
            fs_used = None
    if estimated is None and fs_used is not None:
        estimated = fs_used
    return estimated, fs_total, _repo_status_mount_point(result, repository_subdir=repository_subdir)


def _run_repository_usage_probe(
    *,
    repository: Repository,
    node_id: int,
    payload: dict[str, Any],
    log_scope: str = "storage repo usage probe",
) -> RepositoryUsageProbeResult:
    from apps.node.services.internal.agent_log import log_agent_dispatch, log_agent_exception, log_agent_outcome
    from apps.node.services.interface import run_agent_task_sync

    log_agent_dispatch(
        log_scope,
        node_id=node_id,
        kind="repo.status",
        correlation_type="storage_repository",
        correlation_id=str(repository.id),
        repository_id=repository.id,
        repo_type=repository.repo_type,
    )
    try:
        outcome = run_agent_task_sync(
            organization_id=repository.organization_id,
            node_id=node_id,
            kind="repo.status",
            payload=payload,
            correlation_type="storage_repository",
            correlation_id=str(repository.id),
            wait_timeout_seconds=180,
        )
    except Exception as exc:
        log_agent_exception(
            log_scope,
            node_id=node_id,
            kind="repo.status",
            exc=exc,
            correlation_type="storage_repository",
            correlation_id=str(repository.id),
            repository_id=repository.id,
        )
        return RepositoryUsageProbeResult(None, None, str(exc)[:1000])
    log_agent_outcome(
        log_scope,
        outcome=outcome,
        node_id=node_id,
        kind="repo.status",
        correlation_type="storage_repository",
        correlation_id=str(repository.id),
        repository_id=repository.id,
    )
    if outcome.task.status != "success":
        message = str(getattr(outcome.task, "last_error", "") or "").strip()
        result = outcome.result if isinstance(outcome.result, dict) else {}
        if not message:
            message = str(result.get("error") or result.get("stderr") or "").strip()
        return RepositoryUsageProbeResult(None, None, (message or "repo.status failed")[:1000])
    result = outcome.result if isinstance(outcome.result, dict) else {}
    repository_payload = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    repository_subdir = str(repository_payload.get("subdir") or "").strip()
    estimated, capacity, mount_point = _parse_agent_repo_status_result(
        result,
        repository_subdir=repository_subdir,
    )
    return RepositoryUsageProbeResult(estimated, capacity, mount_point=mount_point)


def agent_repository_usage_probe(repository: Repository) -> tuple[int | None, int | None]:
    """Return (estimated_usage_bytes, filesystem_total_bytes) via repo.status."""
    if repository.status != Repository.Status.CREATED:
        return None, None
    resolved = _agent_repository_payload(repository)
    if resolved is None:
        return None, None
    node_id, payload = resolved
    result = _run_repository_usage_probe(
        repository=repository,
        node_id=node_id,
        payload=payload,
    )
    return result.estimated_usage_bytes, result.capacity_bytes


def _is_unbound_nas_repository(repository: Repository) -> bool:
    return (
        repository.repo_type == Repository.Type.NAS
        and not repository.bind_node_type
        and not repository.bind_node_id
    )


def _direct_nas_agent_config_groups(repository: Repository) -> dict[int, list[int]]:
    backup_config_model = apps.get_model("protection", "BackupConfig")
    groups: dict[int, list[int]] = {}
    rows = (
        backup_config_model.objects.filter(
            organization_id=repository.organization_id,
            repository_id=repository.id,
            source_type="agent",
        )
        .order_by("source_ref_id", "id")
        .values_list("id", "source_ref_id")
    )
    for config_id, source_ref_id in rows:
        try:
            node_id = int(source_ref_id)
        except (TypeError, ValueError):
            continue
        if node_id <= 0:
            continue
        groups.setdefault(node_id, []).append(int(config_id))
    return groups


def _mark_direct_nas_inactive_shards(
    *,
    repository: Repository,
    active_keys: set[tuple[int, str]],
    checked_at,
) -> None:
    qs = RepositoryUsageShard.objects.filter(
        organization_id=repository.organization_id,
        repository_id=repository.id,
        usage_scope=RepositoryUsageShard.Scope.DIRECT_NAS_AGENT,
        is_active=True,
    )
    for shard in qs:
        key = (int(shard.node_id), str(shard.repository_subdir))
        if key in active_keys:
            continue
        shard.is_active = False
        shard.status = RepositoryUsageShard.Status.SKIPPED
        shard.source_config_count = 0
        shard.source_config_ids = []
        shard.last_error = ""
        shard.last_checked_at = checked_at
        shard.save(
            update_fields=[
                "is_active",
                "status",
                "source_config_count",
                "source_config_ids",
                "last_error",
                "last_checked_at",
                "updated_at",
            ]
        )


def _upsert_direct_nas_agent_shard(
    *,
    repository: Repository,
    node_id: int,
    repository_subdir: str,
    source_config_ids: list[int],
    checked_at,
    probe: RepositoryUsageProbeResult | None = None,
    status: str | None = None,
    last_error: str = "",
) -> RepositoryUsageShard:
    defaults: dict[str, Any] = {
        "source_config_count": len(source_config_ids),
        "source_config_ids": source_config_ids,
        "is_active": True,
        "last_checked_at": checked_at,
    }
    if probe is not None and probe.error == "":
        defaults.update({
            "estimated_usage_bytes": max(0, int(probe.estimated_usage_bytes or 0)),
            "capacity_bytes": max(0, int(probe.capacity_bytes or 0)),
            "status": RepositoryUsageShard.Status.SUCCESS,
            "last_error": "",
            "last_success_checked_at": checked_at,
        })
        if probe.mount_point:
            defaults["mount_point"] = str(probe.mount_point)[:1000]
    else:
        defaults.update({
            "status": status or RepositoryUsageShard.Status.FAILED,
            "last_error": str(last_error or (probe.error if probe else ""))[:1000],
        })
    shard, _created = RepositoryUsageShard.objects.update_or_create(
        organization_id=repository.organization_id,
        repository_id=repository.id,
        usage_scope=RepositoryUsageShard.Scope.DIRECT_NAS_AGENT,
        node_id=node_id,
        repository_subdir=repository_subdir,
        defaults=defaults,
    )
    return shard


def _direct_nas_agent_payload(repository: Repository, *, node_id: int, subdir: str) -> dict[str, Any]:
    from apps.storage.services.internal.nas_repository import nas_repository_payload

    return {
        "repository": nas_repository_payload(
            repository=repository,
            subdir=subdir,
            node_id=node_id,
        )
    }


def _sync_direct_nas_agent_usage_shards(repository: Repository) -> tuple[int | None, int | None]:
    from apps.node.models import Node
    from apps.node.models.base import NodeRole
    from apps.storage.services.internal.nas_repository import nas_agent_repository_subdir

    if repository.status != Repository.Status.CREATED:
        return None, None

    checked_at = timezone.now()
    groups = _direct_nas_agent_config_groups(repository)
    active_keys: set[tuple[int, str]] = {
        (node_id, nas_agent_repository_subdir(node_id))
        for node_id in groups
    }
    _mark_direct_nas_inactive_shards(
        repository=repository,
        active_keys=active_keys,
        checked_at=checked_at,
    )

    if not groups:
        return 0, None

    nodes_by_id = {
        node.id: node
        for node in Node.objects.filter(
            organization_id=repository.organization_id,
            role=NodeRole.AGENT,
            id__in=list(groups.keys()),
            is_deleted=False,
        )
    }
    for node_id, source_config_ids in groups.items():
        subdir = nas_agent_repository_subdir(node_id)
        node = nodes_by_id.get(node_id)
        if node is None:
            _upsert_direct_nas_agent_shard(
                repository=repository,
                node_id=node_id,
                repository_subdir=subdir,
                source_config_ids=source_config_ids,
                checked_at=checked_at,
                status=RepositoryUsageShard.Status.SKIPPED,
                last_error="Agent source not found.",
            )
            continue
        if node.status != Node.Status.ONLINE:
            _upsert_direct_nas_agent_shard(
                repository=repository,
                node_id=node_id,
                repository_subdir=subdir,
                source_config_ids=source_config_ids,
                checked_at=checked_at,
                status=RepositoryUsageShard.Status.SKIPPED,
                last_error=f'Agent source "{node.name}" is not online.',
            )
            continue
        probe = _run_repository_usage_probe(
            repository=repository,
            node_id=node.id,
            payload=_direct_nas_agent_payload(repository, node_id=node.id, subdir=subdir),
            log_scope="storage direct nas agent usage probe",
        )
        _upsert_direct_nas_agent_shard(
            repository=repository,
            node_id=node.id,
            repository_subdir=subdir,
            source_config_ids=source_config_ids,
            checked_at=checked_at,
            probe=probe,
        )

    active_shards = RepositoryUsageShard.objects.filter(
        organization_id=repository.organization_id,
        repository_id=repository.id,
        usage_scope=RepositoryUsageShard.Scope.DIRECT_NAS_AGENT,
        is_active=True,
        last_success_checked_at__isnull=False,
    )
    if not active_shards.exists():
        return None, None
    estimated = sum(max(0, int(shard.estimated_usage_bytes or 0)) for shard in active_shards)
    capacities = [
        int(shard.capacity_bytes or 0)
        for shard in active_shards
        if int(shard.capacity_bytes or 0) > 0
    ]
    return estimated, (max(capacities) if capacities else None)


def proxy_fs_filesystem_capacity_bytes(repository: Repository) -> int | None:
    config = repository.config if isinstance(repository.config, dict) else {}
    path = str(config.get("proxy_node_dir") or "").strip()
    node_id = int(repository.bind_node_id or 0)
    if not path or not node_id:
        return None
    stats = agent_path_usage_bytes(
        organization_id=repository.organization_id,
        node_id=node_id,
        path=path,
    )
    if stats is None:
        return None
    return stats[1]


def collect_usage_candidates(repository: Repository) -> tuple[int | None, int | None]:
    """
    Return (estimated_usage_bytes, optional_filesystem_capacity_bytes).
    """
    fs_capacity: int | None = None
    estimated_usage_bytes: int | None = None

    if repository.repo_type == Repository.Type.S3:
        kopia_estimated = kopia_repository_estimated_usage_bytes(repository)
        if kopia_estimated is not None:
            estimated_usage_bytes = max(0, int(kopia_estimated))

    if _is_unbound_nas_repository(repository):
        return _sync_direct_nas_agent_usage_shards(repository)

    if repository.repo_type in (Repository.Type.NAS, Repository.Type.PROXY_FS):
        agent_estimated, agent_fs_total = agent_repository_usage_probe(repository)
        if agent_estimated is not None:
            estimated_usage_bytes = agent_estimated
        if agent_fs_total and agent_fs_total > 0:
            fs_capacity = agent_fs_total
        elif (
            repository.repo_type == Repository.Type.PROXY_FS
            and capacity_bytes_from_config(repository.config) <= 0
        ):
            total = proxy_fs_filesystem_capacity_bytes(repository)
            if total and total > 0:
                fs_capacity = total

    return estimated_usage_bytes, fs_capacity


def sync_repository_usage(repository: Repository, *, persist: bool = True) -> Repository:
    config_capacity = capacity_bytes_from_config(repository.config)
    capacity_changed = False
    if config_capacity > 0 and int(repository.capacity_bytes or 0) != config_capacity:
        repository.capacity_bytes = config_capacity
        capacity_changed = True
    estimated_usage_bytes, fs_capacity = collect_usage_candidates(repository)
    capacity_bytes = int(repository.capacity_bytes or 0)
    if config_capacity <= 0 and fs_capacity and fs_capacity > 0 and capacity_bytes != fs_capacity:
        capacity_bytes = fs_capacity
        capacity_changed = True

    usage_changed = (
        estimated_usage_bytes is not None
        and int(repository.estimated_usage_bytes or 0) != estimated_usage_bytes
    )
    if capacity_changed:
        repository.capacity_bytes = capacity_bytes
    if usage_changed:
        repository.estimated_usage_bytes = estimated_usage_bytes
    repository.last_checked_at = timezone.now()
    update_fields: list[str] = ["last_checked_at"]
    if capacity_changed:
        update_fields.append("capacity_bytes")
    if usage_changed:
        update_fields.append("estimated_usage_bytes")
    update_fields.append("updated_at")
    if persist:
        repository.save(update_fields=update_fields)
    return repository


def _valid_repo_type(value: str | None) -> str | None:
    if value in {choice[0] for choice in Repository.Type.choices}:
        return value
    return None


def _normalize_repository_ids(repository_ids: list[int] | tuple[int, ...] | None) -> list[int]:
    normalized: list[int] = []
    for value in repository_ids or []:
        try:
            repository_id = int(value)
        except (TypeError, ValueError):
            continue
        if repository_id > 0 and repository_id not in normalized:
            normalized.append(repository_id)
    return normalized


def _stale_cutoff(*, force: bool, stale_after_seconds: int | None):
    if force:
        return None
    seconds = int(stale_after_seconds or 0)
    if seconds <= 0:
        return None
    return timezone.now() - timedelta(seconds=seconds)


def _repository_usage_queryset(
    *,
    organization_id: int | None = None,
    repository_ids: list[int] | tuple[int, ...] | None = None,
    repo_type: str | None = None,
    limit: int = 200,
    force: bool = False,
    stale_after_seconds: int | None = None,
):
    qs = Repository.objects.exclude(status=Repository.Status.REMOVED)
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)
    ids = _normalize_repository_ids(repository_ids)
    if ids:
        qs = qs.filter(id__in=ids)
    clean_repo_type = _valid_repo_type(repo_type)
    if clean_repo_type:
        qs = qs.filter(repo_type=clean_repo_type)
    cutoff = _stale_cutoff(force=force, stale_after_seconds=stale_after_seconds)
    if cutoff is not None:
        qs = qs.filter(Q(last_checked_at__isnull=True) | Q(last_checked_at__lt=cutoff))
    return qs.order_by("id")[: max(1, int(limit or 1))]


def sync_organization_repositories(
    *,
    organization_id: int,
    limit: int = 200,
    repository_ids: list[int] | tuple[int, ...] | None = None,
    repo_type: str | None = None,
    force: bool = False,
    stale_after_seconds: int | None = None,
) -> dict[str, Any]:
    ids = _normalize_repository_ids(repository_ids)
    logger.info(
        "repository usage sync org started org_id=%s limit=%s repo_type=%s repository_ids=%s force=%s stale_after_seconds=%s",
        organization_id,
        limit,
        repo_type or "",
        ids,
        force,
        stale_after_seconds,
    )
    qs = _repository_usage_queryset(
        organization_id=organization_id,
        repository_ids=ids,
        repo_type=repo_type,
        limit=limit,
        force=force,
        stale_after_seconds=stale_after_seconds,
    )
    synced = 0
    for repository in qs:
        sync_repository_usage(repository)
        synced += 1
    logger.info(
        "repository usage sync org finished org_id=%s repositories_synced=%s",
        organization_id,
        synced,
    )
    return {"organization_id": organization_id, "repositories_synced": synced}


def sync_all_repositories(
    *,
    limit: int = 500,
    repo_type: str | None = None,
    force: bool = False,
    stale_after_seconds: int | None = None,
) -> dict[str, Any]:
    logger.info(
        "repository usage sync all started limit=%s repo_type=%s force=%s stale_after_seconds=%s",
        limit,
        repo_type or "",
        force,
        stale_after_seconds,
    )
    qs = _repository_usage_queryset(
        repo_type=repo_type,
        limit=limit,
        force=force,
        stale_after_seconds=stale_after_seconds,
    )
    synced = 0
    for repository in qs:
        sync_repository_usage(repository)
        synced += 1
    logger.info("repository usage sync all finished repositories_synced=%s", synced)
    return {"repositories_synced": synced}


def _usage_refresh_lock_key(
    *,
    organization_id: int | None,
    repository_ids: list[int],
    repo_type: str | None,
    force: bool,
) -> str:
    scope = ",".join(str(i) for i in sorted(repository_ids)) if repository_ids else "all"
    return (
        "storage:repository-usage-refresh:"
        f"org:{organization_id or 'all'}:"
        f"type:{repo_type or 'all'}:"
        f"ids:{scope}:"
        f"force:{int(bool(force))}"
    )


def enqueue_repository_usage_refresh(
    *,
    organization_id: int | None = None,
    repository_ids: list[int] | tuple[int, ...] | None = None,
    repo_type: str | None = None,
    limit: int = 200,
    force: bool = False,
    stale_after_seconds: int | None = _DEFAULT_STALE_AFTER_SECONDS,
    trigger: str = "api",
) -> dict[str, Any]:
    ids = _normalize_repository_ids(repository_ids)
    clean_repo_type = _valid_repo_type(repo_type)
    lock_key = _usage_refresh_lock_key(
        organization_id=organization_id,
        repository_ids=ids,
        repo_type=clean_repo_type,
        force=force,
    )
    if not cache.add(lock_key, "1", timeout=_USAGE_REFRESH_DEDUP_TTL_SECONDS):
        logger.info(
            "repository usage refresh deduplicated trigger=%s org_id=%s repo_type=%s repository_ids=%s force=%s",
            trigger,
            organization_id,
            clean_repo_type or "",
            ids,
            force,
        )
        return {
            "queued": False,
            "deduplicated": True,
            "organization_id": organization_id,
            "repo_type": clean_repo_type,
            "repository_ids": ids,
            "limit": limit,
        }

    try:
        from apps.storage.tasks import reconcile_storage_repositories

        async_result = reconcile_storage_repositories.apply_async(
            kwargs={
                "organization_id": organization_id,
                "repository_ids": ids,
                "repo_type": clean_repo_type,
                "limit": max(1, int(limit or 1)),
                "force": bool(force),
                "stale_after_seconds": stale_after_seconds,
            }
        )
    except Exception as exc:
        cache.delete(lock_key)
        logger.exception(
            "repository usage refresh enqueue failed trigger=%s org_id=%s repo_type=%s repository_ids=%s force=%s",
            trigger,
            organization_id,
            clean_repo_type or "",
            ids,
            force,
        )
        return {
            "queued": False,
            "error": str(exc),
            "organization_id": organization_id,
            "repo_type": clean_repo_type,
            "repository_ids": ids,
            "limit": limit,
        }

    logger.info(
        "repository usage refresh queued trigger=%s task_id=%s org_id=%s repo_type=%s repository_ids=%s force=%s stale_after_seconds=%s",
        trigger,
        getattr(async_result, "id", ""),
        organization_id,
        clean_repo_type or "",
        ids,
        force,
        stale_after_seconds,
    )
    return {
        "queued": True,
        "task_id": getattr(async_result, "id", ""),
        "organization_id": organization_id,
        "repo_type": clean_repo_type,
        "repository_ids": ids,
        "limit": limit,
    }
