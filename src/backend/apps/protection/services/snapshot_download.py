from __future__ import annotations

import logging
import os
import threading
import zipfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import close_old_connections, transaction
from django.utils import timezone
from django.utils.text import get_valid_filename

from apps.protection.models import BackupSourceSnapshotDirectory, SnapshotDownloadArtifact
from apps.protection.services.snapshot_browser import (
    SnapshotFileDownload,
    SnapshotBrowserError,
    SnapshotBrowserForbidden,
    _clean_relative_path,
    _get_directory,
    download_snapshot_file,
)
from apps.task.models import Task, TaskResource, TaskStep
from apps.task.services.interface import append_task_step_event, complete_task, create_task, start_task

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_DOWNLOAD_EXPIRES_HOURS = 24
DEFAULT_SNAPSHOT_DOWNLOAD_MAX_BYTES = 200 * 1024 * 1024
DEFAULT_SNAPSHOT_BATCH_DOWNLOAD_MAX_PATHS = 100


def _artifact_root() -> Path:
    """Return the runtime directory for generated snapshot downloads."""
    return Path(settings.MEDIA_ROOT) / "snapshot-downloads"


def _safe_filename(value: str, fallback: str = "download") -> str:
    filename = get_valid_filename(str(value or "").strip())
    return filename or fallback


def _expires_at():
    return timezone.now() + timedelta(hours=DEFAULT_SNAPSHOT_DOWNLOAD_EXPIRES_HOURS)


def _max_download_bytes() -> int:
    raw = getattr(settings, "PROTECTION_SNAPSHOT_DOWNLOAD_MAX_BYTES", DEFAULT_SNAPSHOT_DOWNLOAD_MAX_BYTES)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_SNAPSHOT_DOWNLOAD_MAX_BYTES


def create_snapshot_download_task(
    *,
    organization_id: int,
    directory_id: int,
    path: str,
    trigger_type: str = Task.TriggerType.MANUAL,
) -> Task:
    clean_path = _clean_relative_path(path)
    directory = _get_directory(organization_id=organization_id, directory_id=directory_id)
    if not clean_path and directory.path_type != BackupSourceSnapshotDirectory.PathType.FILE:
        raise ValidationError({"path": "Download path is required."})
    source_snapshot = directory.source_snapshot
    display_path = clean_path or directory.source_path
    task = create_task(
        organization_id=organization_id,
        task_type=Task.Type.SNAPSHOT_DOWNLOAD,
        display_name=f"Download snapshot path {display_path}",
        trigger_type=trigger_type,
        request_payload={
            "source_snapshot_directory_id": directory.id,
            "source_snapshot_id": directory.source_snapshot_id,
            "source_snapshot_uid": source_snapshot.snapshot_uid,
            "repository_id": directory.repository_id,
            "kopia_snapshot_id": directory.kopia_snapshot_id,
            "path": clean_path,
        },
        resources=[
            {
                "resource_type": TaskResource.Type.BACKUP_SOURCE,
                "resource_subtype": source_snapshot.source_type,
                "resource_id": source_snapshot.source_ref_id,
                "is_primary": True,
            },
        ],
        steps=["snapshot_download_restore", "snapshot_download_transfer", "snapshot_download_finalize"],
    )
    _queue_snapshot_download_execution(task_id=task.id)
    return task


def _dedupe_clean_paths(paths: list[str]) -> list[str]:
    clean_paths: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        clean_path = _clean_relative_path(str(raw or ""))
        if not clean_path:
            raise ValidationError({"paths": "Download path is required."})
        if clean_path in seen:
            continue
        clean_paths.append(clean_path)
        seen.add(clean_path)
    return clean_paths


def _has_path_conflict(paths: list[str]) -> bool:
    ordered = sorted(paths)
    for index, current in enumerate(ordered):
        for candidate in ordered[index + 1 :]:
            if not candidate.startswith(f"{current}/"):
                break
            return True
    return False


def create_snapshot_batch_download_task(
    *,
    organization_id: int,
    directory_id: int,
    paths: list[str],
    trigger_type: str = Task.TriggerType.MANUAL,
) -> Task:
    if not paths:
        raise ValidationError({"paths": "At least one download path is required."})
    clean_paths = _dedupe_clean_paths(paths)
    if len(clean_paths) > DEFAULT_SNAPSHOT_BATCH_DOWNLOAD_MAX_PATHS:
        raise ValidationError({"paths": f"At most {DEFAULT_SNAPSHOT_BATCH_DOWNLOAD_MAX_PATHS} paths can be downloaded."})
    if _has_path_conflict(clean_paths):
        raise ValidationError({"paths": "Parent and child paths cannot be downloaded together."})
    directory = _get_directory(organization_id=organization_id, directory_id=directory_id)
    source_snapshot = directory.source_snapshot
    task = create_task(
        organization_id=organization_id,
        task_type=Task.Type.SNAPSHOT_DOWNLOAD,
        display_name=f"Download {len(clean_paths)} snapshot paths",
        trigger_type=trigger_type,
        request_payload={
            "source_snapshot_directory_id": directory.id,
            "source_snapshot_id": directory.source_snapshot_id,
            "source_snapshot_uid": source_snapshot.snapshot_uid,
            "repository_id": directory.repository_id,
            "kopia_snapshot_id": directory.kopia_snapshot_id,
            "paths": clean_paths,
        },
        resources=[
            {
                "resource_type": TaskResource.Type.BACKUP_SOURCE,
                "resource_subtype": source_snapshot.source_type,
                "resource_id": source_snapshot.source_ref_id,
                "is_primary": True,
            },
        ],
        steps=["snapshot_download_restore", "snapshot_download_transfer", "snapshot_download_finalize"],
    )
    _queue_snapshot_download_execution(task_id=task.id)
    return task


def _set_download_step_status(
    *,
    task: Task,
    step_name: str,
    status: str,
    progress: int | float,
    task_progress: int | float | None = None,
    current_step: str | None = None,
) -> None:
    legacy_names = {
        "snapshot_download_restore": "restore",
        "snapshot_download_transfer": "transfer",
        "snapshot_download_finalize": "finalize",
    }
    names = [step_name]
    legacy = legacy_names.get(step_name)
    if legacy:
        names.append(legacy)
    step = TaskStep.objects.filter(task=task, step_name__in=names).order_by("step_index").first()
    if step is not None:
        step.status = status
        step.progress = progress
        step.save(update_fields=["status", "progress"])
    updates: list[str] = []
    if current_step is not None:
        task.current_step = current_step
        updates.append("current_step")
    if task_progress is not None:
        task.progress = task_progress
        updates.append("progress")
    if updates:
        updates.append("updated_at")
        task.save(update_fields=updates)


def _failed_download_progress(step_name: str) -> int:
    if step_name in {"snapshot_download_transfer", "transfer"}:
        return 70
    if step_name in {"snapshot_download_finalize", "finalize"}:
        return 90
    return 10


def _queue_snapshot_download_execution(*, task_id: int) -> None:
    try:
        from apps.protection.tasks.snapshot_download import execute_snapshot_download_task

        execute_snapshot_download_task.delay(task_id=task_id)
        return
    except Exception:
        logger.exception("failed to queue snapshot download celery task; falling back to local thread")
    thread = threading.Thread(
        target=_run_snapshot_download_in_thread,
        kwargs={"task_id": task_id},
        daemon=True,
    )
    thread.start()


def _run_snapshot_download_in_thread(*, task_id: int) -> None:
    close_old_connections()
    try:
        task = Task.objects.get(id=task_id)
        run_snapshot_download_task(task=task)
    except Exception:  # pragma: no cover - defensive logging for background thread
        logger.exception("snapshot download task failed before finalization", extra={"task_id": task_id})
    finally:
        close_old_connections()


def run_snapshot_download_task(*, task: Task) -> dict[str, Any]:
    payload = task.request_payload if isinstance(task.request_payload, dict) else {}
    directory_id = int(payload.get("source_snapshot_directory_id") or 0)
    path = str(payload.get("path") or "")
    paths = payload.get("paths")
    try:
        task = start_task(task_uuid=task.task_uuid, organization_id=task.organization_id)
        _set_download_step_status(
            task=task,
            step_name="snapshot_download_restore",
            status=TaskStep.Status.RUNNING,
            progress=10,
            task_progress=10,
            current_step="snapshot_download_restore",
        )
        append_task_step_event(
            task=task,
            step_name="snapshot_download_restore",
            message="Starting snapshot download",
            metadata={"directory_id": directory_id, "path": path, "paths": paths if isinstance(paths, list) else None},
        )
        if isinstance(paths, list) and paths:
            download = _download_batch_as_zip(
                organization_id=task.organization_id,
                directory_id=directory_id,
                paths=[str(item or "") for item in paths],
                task_id=task.id,
            )
        else:
            download = download_snapshot_file(
                organization_id=task.organization_id,
                directory_id=directory_id,
                path=path,
            )
        if len(download.content) > _max_download_bytes():
            raise SnapshotBrowserError("Snapshot download exceeds the configured size limit.")
        _set_download_step_status(
            task=task,
            step_name="snapshot_download_restore",
            status=TaskStep.Status.SUCCESS,
            progress=100,
            task_progress=55,
            current_step="snapshot_download_transfer",
        )
        _set_download_step_status(
            task=task,
            step_name="snapshot_download_transfer",
            status=TaskStep.Status.RUNNING,
            progress=40,
            task_progress=70,
        )
        artifact = _persist_artifact(
            task=task,
            directory_id=directory_id,
            path=path or ",".join(str(item or "") for item in paths or []),
            download=download,
        )
        _set_download_step_status(
            task=task,
            step_name="snapshot_download_transfer",
            status=TaskStep.Status.SUCCESS,
            progress=100,
            task_progress=90,
            current_step="snapshot_download_finalize",
        )
        result = {
            "artifact_id": artifact.id,
            "filename": artifact.filename,
            "content_type": artifact.content_type,
            "size_bytes": artifact.size_bytes,
            "expires_at": artifact.expires_at.isoformat(),
        }
        append_task_step_event(
            task=task,
            step_name="snapshot_download_transfer",
            message="Snapshot download artifact is ready",
            metadata=result,
        )
        _set_download_step_status(
            task=task,
            step_name="snapshot_download_finalize",
            status=TaskStep.Status.SUCCESS,
            progress=100,
            task_progress=100,
        )
        complete_task(
            task_uuid=task.task_uuid,
            organization_id=task.organization_id,
            status=Task.Status.SUCCESS,
            result_payload=result,
        )
        return result
    except (SnapshotBrowserError, SnapshotBrowserForbidden, ValidationError) as exc:
        message = str(exc)
        failed_step = str(task.current_step or "snapshot_download_restore")
        failed_progress = _failed_download_progress(failed_step)
        _set_download_step_status(
            task=task,
            step_name=failed_step,
            status=TaskStep.Status.FAILED,
            progress=100,
            task_progress=failed_progress,
            current_step=failed_step,
        )
        complete_task(
            task_uuid=task.task_uuid,
            organization_id=task.organization_id,
            status=Task.Status.FAILED,
            progress=failed_progress,
            error_code="SNAPSHOT_DOWNLOAD_FAILED",
            error_message=message,
        )
        return {"error": message}


def _download_batch_as_zip(*, organization_id: int, directory_id: int, paths: list[str], task_id: int) -> SnapshotFileDownload:
    clean_paths = _dedupe_clean_paths(paths)
    if _has_path_conflict(clean_paths):
        raise ValidationError({"paths": "Parent and child paths cannot be downloaded together."})
    buffer = BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for clean_path in clean_paths:
            download = download_snapshot_file(
                organization_id=organization_id,
                directory_id=directory_id,
                path=clean_path,
            )
            if download.content_type == "application/zip":
                _append_nested_zip(
                    archive=archive,
                    content=download.content,
                    prefix=clean_path,
                    used_names=used_names,
                )
            else:
                entry_name = _unique_zip_name(clean_path, used_names)
                archive.writestr(entry_name, download.content)
    filename = _safe_filename(f"snapshot-download-{task_id}.zip", "snapshot-download.zip")
    return SnapshotFileDownload(
        filename=filename,
        content=buffer.getvalue(),
        content_type="application/zip",
    )


def _append_nested_zip(*, archive: zipfile.ZipFile, content: bytes, prefix: str, used_names: set[str]) -> None:
    try:
        nested = zipfile.ZipFile(BytesIO(content), "r")
    except zipfile.BadZipFile:
        entry_name = _unique_zip_name(f"{prefix}.zip", used_names)
        archive.writestr(entry_name, content)
        return
    with nested:
        for info in nested.infolist():
            nested_name = _clean_zip_entry_name(info.filename)
            if not nested_name:
                continue
            entry_name = _unique_zip_name(f"{prefix}/{nested_name}".rstrip("/"), used_names)
            if info.is_dir():
                archive.writestr(entry_name.rstrip("/") + "/", b"")
            else:
                archive.writestr(entry_name, nested.read(info))


def _clean_zip_entry_name(value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return ""
    return "/".join(parts)


def _unique_zip_name(name: str, used_names: set[str]) -> str:
    clean_name = _clean_zip_entry_name(name) or "download"
    candidate = clean_name
    stem = Path(clean_name).stem
    suffix = Path(clean_name).suffix
    parent = str(Path(clean_name).parent).replace("\\", "/")
    if parent == ".":
        parent = ""
    counter = 2
    while candidate in used_names:
        base = f"{stem}-{counter}{suffix}"
        candidate = f"{parent}/{base}" if parent else base
        counter += 1
    used_names.add(candidate)
    return candidate


def _persist_artifact(*, task: Task, directory_id: int, path: str, download) -> SnapshotDownloadArtifact:
    filename = _safe_filename(download.filename)
    task_dir = _artifact_root() / str(task.organization_id) / str(task.task_uuid)
    task_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = task_dir / filename
    artifact_path.write_bytes(download.content)
    with transaction.atomic():
        return SnapshotDownloadArtifact.objects.create(
            task=task,
            organization_id=task.organization_id,
            source_snapshot_directory_id=directory_id,
            relative_path=path,
            filename=filename,
            content_type=download.content_type or "application/octet-stream",
            size_bytes=len(download.content),
            storage_path=str(artifact_path),
            expires_at=_expires_at(),
        )


def get_snapshot_download_artifact(*, organization_id: int, artifact_id: int) -> SnapshotDownloadArtifact | None:
    return SnapshotDownloadArtifact.objects.filter(
        organization_id=organization_id,
        id=artifact_id,
    ).select_related("task").first()


def mark_artifact_downloaded(*, artifact: SnapshotDownloadArtifact) -> None:
    artifact.downloaded_at = timezone.now()
    artifact.save(update_fields=["downloaded_at", "updated_at"])


def cleanup_expired_snapshot_download_artifacts(*, now=None, limit: int = 1000) -> int:
    cutoff = now or timezone.now()
    artifacts = list(
        SnapshotDownloadArtifact.objects.filter(
            status=SnapshotDownloadArtifact.Status.READY,
            expires_at__lte=cutoff,
        ).order_by("expires_at", "id")[: max(1, limit)]
    )
    cleaned = 0
    for artifact in artifacts:
        try:
            if artifact.storage_path:
                os.remove(artifact.storage_path)
        except FileNotFoundError:
            pass
        artifact.status = SnapshotDownloadArtifact.Status.EXPIRED
        artifact.save(update_fields=["status", "updated_at"])
        cleaned += 1
    return cleaned
