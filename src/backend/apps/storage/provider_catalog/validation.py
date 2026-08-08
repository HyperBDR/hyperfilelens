"""Selected-region Provider validation, retry, recovery, and cleanup services."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from celery import current_app
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.storage.conf import (
    provider_validation_retention_seconds,
    provider_validation_run_ttl_seconds,
)
from apps.storage.provider_catalog.catalog import effective_provider_records
from apps.storage.provider_catalog.cloud_validation import (
    ProviderRegionValidationError,
    ProviderValidationCancelled,
    RegionValidationContext,
    cleanup_region,
    validate_region,
)
from apps.storage.provider_catalog.credentials import (
    ProviderCredentials,
    ProviderCredentialUnavailable,
    delete_validation_credentials,
    load_validation_credentials,
    store_validation_credentials,
)
from apps.storage.provider_catalog.diff import provider_diff
from apps.storage.provider_catalog.errors import (
    ProviderCatalogConflictError,
    ProviderCatalogValidationError,
    ProviderEndpointPolicyError,
)
from apps.storage.provider_catalog.locks import lock_provider_ids
from apps.storage.provider_catalog.models import (
    StorageProviderRegionValidation,
    StorageProviderValidationRun,
)
from apps.storage.provider_catalog.schema import (
    CURRENT_SCHEMA_VERSION,
    normalize_provider,
    provider_checksum,
)
from apps.storage.provider_catalog.security import sanitize_cloud_error
from apps.task.models import Task, TaskStep
from apps.task.services.interface import append_task_event, create_task


VALIDATION_TASK_NAME = "apps.storage.tasks.run_storage_provider_validation"
CLEANUP_TASK_NAME = "apps.storage.tasks.cleanup_storage_provider_validation"
VALIDATION_QUEUE = "storage.provider-validation"
MAX_SELECTED_REGIONS = 10

REPLACEABLE_RUN_STATUSES = {
    StorageProviderValidationRun.Status.VALIDATION_FAILED,
    StorageProviderValidationRun.Status.PASSED,
    StorageProviderValidationRun.Status.CANCELLED,
    StorageProviderValidationRun.Status.EXPIRED,
}
ACTIVE_RUN_STATUSES = {
    StorageProviderValidationRun.Status.PENDING,
    StorageProviderValidationRun.Status.VALIDATING,
    StorageProviderValidationRun.Status.CANCELLING,
}
SAFE_TERMINAL_STATUSES = {
    StorageProviderValidationRun.Status.VALIDATION_FAILED,
    StorageProviderValidationRun.Status.CANCELLED,
    StorageProviderValidationRun.Status.EXPIRED,
}


def _conflict(message: str, code: str) -> None:
    exc = ProviderCatalogConflictError(message)
    exc.code = code
    raise exc


def _enqueue(task_name: str, run_id: UUID | str) -> None:
    current_app.send_task(task_name, args=[str(run_id)], queue=VALIDATION_QUEUE)


def _credentials(access_key_id: str, secret_access_key: str) -> ProviderCredentials:
    access_key_id = str(access_key_id or "").strip()
    secret_access_key = str(secret_access_key or "")
    if not access_key_id or not secret_access_key:
        raise ProviderCatalogValidationError(
            "Access key ID and secret access key are required."
        )
    if len(access_key_id) > 256 or len(secret_access_key) > 512:
        raise ProviderCatalogValidationError("Cloud credentials exceed the size limit.")
    return ProviderCredentials(access_key_id, secret_access_key)


def _selected_regions(provider: dict[str, Any], region_ids: list[str]) -> list[dict]:
    if not isinstance(region_ids, list) or not 1 <= len(region_ids) <= MAX_SELECTED_REGIONS:
        raise ProviderCatalogValidationError(
            f"Select between 1 and {MAX_SELECTED_REGIONS} Regions for validation."
        )
    if any(not isinstance(item, str) or not item for item in region_ids):
        raise ProviderCatalogValidationError("Region IDs must be non-empty strings.")
    if len(region_ids) != len(set(region_ids)):
        raise ProviderCatalogValidationError("Region IDs must be unique.")
    region_map = {item["id"]: item for item in provider["regions"]}
    unknown = [item for item in region_ids if item not in region_map]
    if unknown:
        raise ProviderCatalogValidationError(
            f"Unknown validation Region IDs: {', '.join(unknown)}."
        )
    regions = [region_map[item] for item in region_ids]
    if any(item.get("driver") != "s3" for item in regions):
        raise ProviderCatalogValidationError(
            "Only S3 Provider Regions support managed validation."
        )
    return regions


def _task_for_run(run: StorageProviderValidationRun) -> Task:
    return Task.objects.get(pk=run.task_id)


def _reset_task(task: Task, *, current_step: str, message: str) -> None:
    task.status = Task.Status.PENDING
    task.progress = Decimal("0.00")
    task.current_step = current_step
    task.result_payload = None
    task.error_code = None
    task.error_message = None
    task.started_at = None
    task.finished_at = None
    task.save(
        update_fields=[
            "status",
            "progress",
            "current_step",
            "result_payload",
            "error_code",
            "error_message",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )
    task.steps.update(status=TaskStep.Status.PENDING, progress=Decimal("0.00"))
    append_task_event(task=task, message=message)


def _start_task(task: Task, *, step: str) -> None:
    task.status = Task.Status.RUNNING
    task.current_step = step
    task.started_at = task.started_at or timezone.now()
    task.finished_at = None
    task.save(
        update_fields=[
            "status",
            "current_step",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )
    task.steps.filter(step_name=step).update(status=TaskStep.Status.RUNNING)


def _region_counts(run: StorageProviderValidationRun) -> dict[str, int]:
    statuses = list(run.region_validations.values_list("status", flat=True))
    return {
        "region_count": len(statuses),
        "completed_region_count": sum(
            status
            in {
                StorageProviderRegionValidation.Status.SUCCESS,
                StorageProviderRegionValidation.Status.FAILED,
                StorageProviderRegionValidation.Status.CANCELLED,
            }
            for status in statuses
        ),
        "failed_region_count": sum(
            status
            in {
                StorageProviderRegionValidation.Status.FAILED,
                StorageProviderRegionValidation.Status.CLEANUP_FAILED,
            }
            for status in statuses
        ),
    }


def _coverage(run: StorageProviderValidationRun) -> str:
    selected = set(run.region_validations.values_list("region_id", flat=True))
    candidate = {
        item["id"] for item in (run.candidate_config or {}).get("regions", [])
    }
    return "complete" if selected == candidate else "partial"


def _finish_task(
    task: Task,
    *,
    status: str,
    result: str,
    run: StorageProviderValidationRun,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    counts = _region_counts(run)
    task.status = status
    task.progress = Decimal("100.00")
    task.result_payload = {
        "run_id": str(run.id),
        "provider_id": run.provider_id,
        "result": result,
        "coverage": _coverage(run) if result == "passed" else None,
        **counts,
    }
    task.error_code = error_code
    task.error_message = error_message
    task.finished_at = timezone.now()
    task.save(
        update_fields=[
            "status",
            "progress",
            "result_payload",
            "error_code",
            "error_message",
            "finished_at",
            "updated_at",
        ]
    )
    step_status = (
        TaskStep.Status.SUCCESS if status == Task.Status.SUCCESS else TaskStep.Status.FAILED
    )
    task.steps.filter(status=TaskStep.Status.RUNNING).update(
        status=step_status,
        progress=Decimal("100.00"),
    )
    append_task_event(
        task=task,
        message=f"Storage Provider validation {result}",
        metadata={"provider_id": run.provider_id, "result": result, **counts},
    )


def write_validation_run_audit(
    run: StorageProviderValidationRun,
    *,
    result: str,
) -> None:
    from common.platform_audit import write_platform_audit_log

    write_platform_audit_log(
        action="storage_provider.validation.result",
        target_type="storage_provider_validation_run",
        target_id=str(run.id),
        actor_id=run.requested_by_id,
        details={
            "provider_id": run.provider_id,
            "run_id": str(run.id),
            "candidate_checksum": run.candidate_checksum,
            "coverage": _coverage(run) if run.candidate_config else None,
            "result": result,
            "error_code": run.error_code,
            "started_at": run.created_at.isoformat() if run.created_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            **_region_counts(run),
        },
        result=(
            "success"
            if result in {"passed", "cancelled", "expired", "replaced", "applied"}
            else "failure"
        ),
    )


def _old_run_is_safe(run: StorageProviderValidationRun) -> bool:
    return (
        run.status in REPLACEABLE_RUN_STATUSES
        and not run.region_validations.filter(
            status__in=[
                StorageProviderRegionValidation.Status.RUNNING,
                StorageProviderRegionValidation.Status.CLEANUP_FAILED,
            ]
        ).exists()
        and not run.region_validations.filter(bucket_name__isnull=False)
        .exclude(bucket_name="")
        .exists()
    )


def create_validation_run(
    *,
    provider_id: str,
    region_ids: list[str],
    access_key_id: str,
    secret_access_key: str,
    requested_by_id: int,
    candidate_config: dict[str, Any],
) -> StorageProviderValidationRun:
    credentials = _credentials(access_key_id, secret_access_key)
    normalized_candidate = normalize_provider(candidate_config)
    if normalized_candidate["id"] != provider_id:
        raise ProviderCatalogValidationError(
            "Candidate Provider ID does not match the validation target."
        )
    selected_regions = _selected_regions(normalized_candidate, region_ids)

    run_id = uuid4()
    old_run_id: UUID | None = None
    try:
        store_validation_credentials(run_id, credentials)
        with transaction.atomic():
            lock_provider_ids([provider_id])
            old = (
                StorageProviderValidationRun.objects.select_for_update()
                .filter(provider_id=provider_id)
                .first()
            )
            if old is not None:
                if old.status == StorageProviderValidationRun.Status.CLEANUP_REQUIRED:
                    _conflict(
                        "The current Provider run requires cleanup before replacement.",
                        "PROVIDER_VALIDATION_CLEANUP_REQUIRED",
                    )
                if old.status in ACTIVE_RUN_STATUSES or not _old_run_is_safe(old):
                    _conflict(
                        "The current Provider run must finish or be cancelled first.",
                        "PROVIDER_VALIDATION_ACTIVE",
                    )
                old_run_id = old.id
                write_validation_run_audit(old, result="replaced")
                old.delete()

            task = create_task(
                organization_id=None,
                task_type=Task.Type.STORAGE_PROVIDER_VALIDATION,
                display_name=f"Validate storage Provider {provider_id}",
                trigger_type=Task.TriggerType.MANUAL,
                request_payload={
                    "run_id": str(run_id),
                    "provider_id": provider_id,
                    "region_ids": region_ids,
                },
                steps=["validate_regions", "cleanup_resources", "await_review"],
            )
            run = StorageProviderValidationRun.objects.create(
                id=run_id,
                task_id=task.id,
                provider_id=provider_id,
                schema_version=CURRENT_SCHEMA_VERSION,
                candidate_config=normalized_candidate,
                candidate_checksum=provider_checksum(normalized_candidate),
                requested_by_id=requested_by_id,
                expires_at=timezone.now()
                + timedelta(seconds=provider_validation_run_ttl_seconds()),
            )
            StorageProviderRegionValidation.objects.bulk_create(
                [
                    StorageProviderRegionValidation(
                        run=run,
                        region_id=region["id"],
                        region_group=region["region_group"],
                        region_group_en=region["region_group_en"],
                        external_endpoint=region["external_endpoint"],
                        internal_endpoint=region["internal_endpoint"],
                        driver=region["driver"],
                        s3_url_style=region["s3_url_style"],
                        use_tls=region["use_tls"],
                    )
                    for region in selected_regions
                ]
            )
    except (ProviderCatalogConflictError, ProviderCatalogValidationError):
        delete_validation_credentials(run_id)
        raise
    except Exception as exc:
        delete_validation_credentials(run_id)
        raise ProviderCatalogValidationError(
            "Temporary validation credentials or run state could not be stored."
        ) from exc

    if old_run_id is not None:
        delete_validation_credentials(old_run_id)
    try:
        _enqueue(VALIDATION_TASK_NAME, run.id)
    except Exception as exc:
        with transaction.atomic():
            run = StorageProviderValidationRun.objects.select_for_update().get(pk=run.id)
            run.error_code = "VALIDATION_DISPATCH_FAILED"
            run.error_message = "Validation dispatch failed and is awaiting recovery."
            run.save(update_fields=["error_code", "error_message", "updated_at"])
        raise ProviderCatalogValidationError(
            "Validation was saved but could not be dispatched; recovery will retry it."
        ) from exc
    return run


def cancel_validation_run(
    *, run_id: UUID | str, requested_by_id: int
) -> StorageProviderValidationRun:
    enqueue_cleanup = False
    with transaction.atomic():
        run = StorageProviderValidationRun.objects.select_for_update().get(pk=run_id)
        if run.requested_by_id != requested_by_id:
            _conflict("Validation run belongs to another operator.", "RUN_USER_MISMATCH")
        if run.status in {
            StorageProviderValidationRun.Status.CANCELLED,
            StorageProviderValidationRun.Status.EXPIRED,
        }:
            return run
        if run.status == StorageProviderValidationRun.Status.CANCELLING:
            return run
        enqueue_cleanup = run.status != StorageProviderValidationRun.Status.VALIDATING
        run.status = StorageProviderValidationRun.Status.CANCELLING
        run.finished_at = None
        run.error_code = None
        run.error_message = None
        run.save()
        _reset_task(
            _task_for_run(run),
            current_step="cleanup_resources",
            message="Provider validation cancellation requested",
        )
    if enqueue_cleanup:
        _enqueue(CLEANUP_TASK_NAME, run.id)
    return run


def retry_validation_run(
    *,
    run_id: UUID | str,
    requested_by_id: int,
    access_key_id: str,
    secret_access_key: str,
) -> StorageProviderValidationRun:
    credentials = _credentials(access_key_id, secret_access_key)
    with transaction.atomic():
        run = StorageProviderValidationRun.objects.select_for_update().get(pk=run_id)
        if run.requested_by_id != requested_by_id:
            _conflict("Validation run belongs to another operator.", "RUN_USER_MISMATCH")
        if run.status not in {
            StorageProviderValidationRun.Status.VALIDATION_FAILED,
            StorageProviderValidationRun.Status.CLEANUP_REQUIRED,
        }:
            _conflict(
                "Only failed validation or cleanup can be retried.",
                "RUN_STATE_CONFLICT",
            )
        cleanup_only = run.status == StorageProviderValidationRun.Status.CLEANUP_REQUIRED
        try:
            store_validation_credentials(run.id, credentials)
        except Exception as exc:
            raise ProviderCatalogValidationError(
                "Temporary validation credentials could not be stored."
            ) from exc
        run.status = (
            StorageProviderValidationRun.Status.CANCELLING
            if cleanup_only
            else StorageProviderValidationRun.Status.PENDING
        )
        run.finished_at = None
        run.error_code = None
        run.error_message = None
        run.expires_at = timezone.now() + timedelta(
            seconds=provider_validation_run_ttl_seconds()
        )
        run.save()
        if not cleanup_only:
            run.region_validations.exclude(
                status=StorageProviderRegionValidation.Status.SUCCESS
            ).update(
                status=StorageProviderRegionValidation.Status.PENDING,
                current_step=None,
                error_code=None,
                error_message=None,
                started_at=None,
                finished_at=None,
            )
        _reset_task(
            _task_for_run(run),
            current_step="cleanup_resources" if cleanup_only else "validate_regions",
            message="Provider validation retry queued",
        )
    _enqueue(CLEANUP_TASK_NAME if cleanup_only else VALIDATION_TASK_NAME, run.id)
    return run


def _set_run_failure(
    run: StorageProviderValidationRun,
    *,
    code: str,
    message: str,
    cleanup_required: bool,
) -> None:
    finished_at = timezone.now()
    run.region_validations.filter(
        status=StorageProviderRegionValidation.Status.RUNNING,
    ).exclude(
        Q(bucket_name__isnull=True) | Q(bucket_name="")
    ).update(
        status=StorageProviderRegionValidation.Status.CLEANUP_FAILED,
        error_code=code,
        error_message=message,
        finished_at=finished_at,
        updated_at=finished_at,
    )
    run.region_validations.filter(
        status=StorageProviderRegionValidation.Status.RUNNING,
    ).update(
        status=StorageProviderRegionValidation.Status.FAILED,
        error_code=code,
        error_message=message,
        finished_at=finished_at,
        updated_at=finished_at,
    )
    run.status = (
        StorageProviderValidationRun.Status.CLEANUP_REQUIRED
        if cleanup_required
        else StorageProviderValidationRun.Status.VALIDATION_FAILED
    )
    run.error_code = code
    run.error_message = message
    run.finished_at = finished_at
    run.save()
    _finish_task(
        _task_for_run(run),
        status=Task.Status.FAILED,
        result="cleanup_required" if cleanup_required else "validation_failed",
        run=run,
        error_code=code,
        error_message=message,
    )
    write_validation_run_audit(
        run, result="cleanup_required" if cleanup_required else "validation_failed"
    )
    if not cleanup_required:
        delete_validation_credentials(run.id)


def _run_cancelled(run_id: UUID | str) -> bool:
    return (
        StorageProviderValidationRun.objects.filter(pk=run_id)
        .values_list("status", flat=True)
        .first()
        == StorageProviderValidationRun.Status.CANCELLING
    )


def _row_region(row: StorageProviderRegionValidation) -> dict[str, Any]:
    return {
        "id": row.region_id,
        "region_group": row.region_group,
        "region_group_en": row.region_group_en,
        "external_endpoint": row.external_endpoint,
        "internal_endpoint": row.internal_endpoint,
        "driver": row.driver,
        "s3_url_style": row.s3_url_style,
        "use_tls": row.use_tls,
    }


def execute_validation_run(run_id: UUID | str) -> None:
    credentials: ProviderCredentials | None = None
    try:
        credentials = load_validation_credentials(run_id)
        cancel_requested = False
        with transaction.atomic():
            run = StorageProviderValidationRun.objects.select_for_update().get(pk=run_id)
            if run.status == StorageProviderValidationRun.Status.CANCELLING:
                cancel_requested = True
            elif run.status != StorageProviderValidationRun.Status.PENDING:
                return
            else:
                run.status = StorageProviderValidationRun.Status.VALIDATING
                run.error_code = None
                run.error_message = None
                run.finished_at = None
                run.save()
                _start_task(_task_for_run(run), step="validate_regions")
        if cancel_requested:
            cleanup_validation_run(run_id)
            return

        if not run.candidate_config:
            raise ProviderRegionValidationError(
                "CANDIDATE_MISSING", "Validation candidate is unavailable."
            )
        for row in run.region_validations.order_by("id"):
            if _run_cancelled(run_id):
                break
            if row.status == StorageProviderRegionValidation.Status.SUCCESS and not row.bucket_name:
                continue
            row.status = StorageProviderRegionValidation.Status.RUNNING
            row.current_step = StorageProviderRegionValidation.Step.CREATE_BUCKET
            row.error_code = None
            row.error_message = None
            row.started_at = timezone.now()
            row.finished_at = None
            row.save()

            def set_step(value: str, *, row_id=row.id) -> None:
                StorageProviderRegionValidation.objects.filter(pk=row_id).update(
                    current_step=value, updated_at=timezone.now()
                )

            def set_bucket(value: str | None, *, row_id=row.id) -> None:
                StorageProviderRegionValidation.objects.filter(pk=row_id).update(
                    bucket_name=value, updated_at=timezone.now()
                )

            context = RegionValidationContext(
                run_id=run.id,
                provider_id=run.provider_id,
                region=_row_region(row),
                credentials=credentials,
            )
            try:
                validate_region(
                    context,
                    step=set_step,
                    set_bucket=set_bucket,
                    cancelled=lambda: _run_cancelled(run_id),
                )
            except ProviderValidationCancelled:
                row.refresh_from_db()
                row.status = StorageProviderRegionValidation.Status.CANCELLED
                row.error_code = "VALIDATION_CANCELLED"
                row.error_message = "Validation was cancelled."
                row.finished_at = timezone.now()
                row.save()
                break
            except ProviderRegionValidationError as exc:
                row.refresh_from_db()
                row.status = (
                    StorageProviderRegionValidation.Status.CLEANUP_FAILED
                    if exc.cleanup_required
                    else StorageProviderRegionValidation.Status.FAILED
                )
                row.error_code = exc.code
                row.error_message = sanitize_cloud_error(
                    exc.message,
                    secrets=(credentials.access_key_id, credentials.secret_access_key),
                )
                row.finished_at = timezone.now()
                row.save()
                if exc.cleanup_required:
                    break
            else:
                row.refresh_from_db()
                row.status = StorageProviderRegionValidation.Status.SUCCESS
                row.current_step = StorageProviderRegionValidation.Step.VERIFY_CLEANUP
                row.error_code = None
                row.error_message = None
                row.finished_at = timezone.now()
                row.save()

        cancel_requested = False
        with transaction.atomic():
            run = StorageProviderValidationRun.objects.select_for_update().get(pk=run_id)
            if run.status == StorageProviderValidationRun.Status.CANCELLING:
                cancel_requested = True
            else:
                rows = list(run.region_validations.all())
                cleanup_required = any(
                    row.status == StorageProviderRegionValidation.Status.CLEANUP_FAILED
                    or bool(row.bucket_name)
                    for row in rows
                )
                failed = any(
                    row.status != StorageProviderRegionValidation.Status.SUCCESS
                    for row in rows
                )
                if cleanup_required:
                    _set_run_failure(
                        run,
                        code="CLEANUP_REQUIRED",
                        message="One or more Regions require manual cleanup retry.",
                        cleanup_required=True,
                    )
                elif failed:
                    _set_run_failure(
                        run,
                        code="VALIDATION_FAILED",
                        message="One or more Provider Regions failed validation.",
                        cleanup_required=False,
                    )
                else:
                    run.status = StorageProviderValidationRun.Status.PASSED
                    run.finished_at = timezone.now()
                    run.error_code = None
                    run.error_message = None
                    run.save()
                    _finish_task(
                        _task_for_run(run),
                        status=Task.Status.SUCCESS,
                        result="passed",
                        run=run,
                    )
                    write_validation_run_audit(run, result="passed")
                    delete_validation_credentials(run.id)
        if cancel_requested:
            cleanup_validation_run(run_id)
    except StorageProviderValidationRun.DoesNotExist:
        return
    except ProviderCredentialUnavailable as exc:
        with transaction.atomic():
            run = StorageProviderValidationRun.objects.select_for_update().filter(pk=run_id).first()
            if run is None:
                return
            cleanup_required = run.region_validations.filter(
                bucket_name__isnull=False
            ).exclude(bucket_name="").exists()
            _set_run_failure(
                run,
                code="CREDENTIALS_UNAVAILABLE",
                message=sanitize_cloud_error(str(exc)),
                cleanup_required=cleanup_required,
            )
    except ProviderRegionValidationError as exc:
        with transaction.atomic():
            run = StorageProviderValidationRun.objects.select_for_update().filter(pk=run_id).first()
            if run is None:
                return
            _set_run_failure(
                run,
                code=exc.code,
                message=sanitize_cloud_error(
                    exc.message,
                    secrets=(
                        credentials.access_key_id if credentials else "",
                        credentials.secret_access_key if credentials else "",
                    ),
                ),
                cleanup_required=exc.cleanup_required,
            )
    except ProviderEndpointPolicyError as exc:
        with transaction.atomic():
            run = StorageProviderValidationRun.objects.select_for_update().filter(pk=run_id).first()
            if run is None:
                return
            _set_run_failure(
                run,
                code=exc.code,
                message=sanitize_cloud_error(exc.message),
                cleanup_required=False,
            )
    except Exception as exc:
        with transaction.atomic():
            run = StorageProviderValidationRun.objects.select_for_update().filter(pk=run_id).first()
            if run is None:
                return
            cleanup_required = run.region_validations.filter(
                bucket_name__isnull=False
            ).exclude(bucket_name="").exists()
            _set_run_failure(
                run,
                code="VALIDATION_FAILED",
                message=sanitize_cloud_error(
                    str(exc),
                    secrets=(
                        credentials.access_key_id if credentials else "",
                        credentials.secret_access_key if credentials else "",
                    ),
                ),
                cleanup_required=cleanup_required,
            )


def cleanup_validation_run(run_id: UUID | str) -> None:
    try:
        run = StorageProviderValidationRun.objects.get(pk=run_id)
    except StorageProviderValidationRun.DoesNotExist:
        return

    rows_with_resources = run.region_validations.exclude(bucket_name__isnull=True).exclude(
        bucket_name=""
    )
    credentials: ProviderCredentials | None = None
    if rows_with_resources.exists():
        try:
            credentials = load_validation_credentials(run_id)
        except ProviderCredentialUnavailable as exc:
            with transaction.atomic():
                run = StorageProviderValidationRun.objects.select_for_update().get(pk=run_id)
                _set_run_failure(
                    run,
                    code="CREDENTIALS_UNAVAILABLE",
                    message=sanitize_cloud_error(str(exc)),
                    cleanup_required=True,
                )
            return

    cleanup_failed = False
    for row in rows_with_resources:
        def set_step(value: str, *, row_id=row.id) -> None:
            StorageProviderRegionValidation.objects.filter(pk=row_id).update(
                current_step=value, updated_at=timezone.now()
            )

        def set_bucket(value: str | None, *, row_id=row.id) -> None:
            StorageProviderRegionValidation.objects.filter(pk=row_id).update(
                bucket_name=value, updated_at=timezone.now()
            )

        assert credentials is not None
        context = RegionValidationContext(
            run_id=run.id,
            provider_id=run.provider_id,
            region=_row_region(row),
            credentials=credentials,
        )
        try:
            cleanup_region(
                context,
                bucket_name=str(row.bucket_name),
                step=set_step,
                set_bucket=set_bucket,
            )
        except Exception as exc:
            cleanup_failed = True
            row.refresh_from_db()
            row.status = StorageProviderRegionValidation.Status.CLEANUP_FAILED
            row.error_code = getattr(exc, "code", "BUCKET_CLEANUP_FAILED")
            row.error_message = sanitize_cloud_error(
                getattr(exc, "message", str(exc)),
                secrets=(credentials.access_key_id, credentials.secret_access_key),
            )
            row.finished_at = timezone.now()
            row.save()
        else:
            row.refresh_from_db()
            row.status = StorageProviderRegionValidation.Status.CANCELLED
            row.error_code = None
            row.error_message = None
            row.finished_at = timezone.now()
            row.save()

    now = timezone.now()
    run.region_validations.filter(
        Q(bucket_name__isnull=True) | Q(bucket_name="")
    ).exclude(
        status=StorageProviderRegionValidation.Status.SUCCESS
    ).update(
        status=StorageProviderRegionValidation.Status.CANCELLED,
        current_step=None,
        error_code=None,
        error_message=None,
        finished_at=now,
        updated_at=now,
    )

    with transaction.atomic():
        run = StorageProviderValidationRun.objects.select_for_update().get(pk=run_id)
        if cleanup_failed or run.region_validations.filter(
            bucket_name__isnull=False
        ).exclude(bucket_name="").exists():
            _set_run_failure(
                run,
                code="CLEANUP_REQUIRED",
                message="One or more temporary Buckets still require cleanup.",
                cleanup_required=True,
            )
            return
        run.status = StorageProviderValidationRun.Status.CANCELLED
        run.candidate_config = None
        run.candidate_checksum = None
        run.error_code = None
        run.error_message = None
        run.finished_at = timezone.now()
        run.save()
        _finish_task(
            _task_for_run(run),
            status=Task.Status.CANCELLED,
            result="cancelled",
            run=run,
        )
        write_validation_run_audit(run, result="cancelled")
    delete_validation_credentials(run_id)


def validation_run_diff(run: StorageProviderValidationRun) -> dict | None:
    if not run.candidate_config:
        return None
    current = effective_provider_records().get(run.provider_id)
    return provider_diff(
        provider_id=run.provider_id,
        before=current["config"] if current else None,
        after=run.candidate_config,
    )


def serialize_validation_run(run: StorageProviderValidationRun) -> dict[str, Any]:
    task = Task.objects.filter(pk=run.task_id).only("task_uuid").first()
    regions = [
        {
            "id": row.id,
            "region_id": row.region_id,
            "region_group": row.region_group,
            "region_group_en": row.region_group_en,
            "external_endpoint": row.external_endpoint,
            "internal_endpoint": row.internal_endpoint,
            "driver": row.driver,
            "s3_url_style": row.s3_url_style,
            "use_tls": row.use_tls,
            "status": row.status,
            "current_step": row.current_step,
            "error_code": row.error_code,
            "error_message": row.error_message,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "updated_at": row.updated_at,
        }
        for row in run.region_validations.order_by("id")
    ]
    return {
        "id": str(run.id),
        "task_id": run.task_id,
        "task_uuid": str(task.task_uuid) if task else None,
        "provider_id": run.provider_id,
        "schema_version": run.schema_version,
        "status": run.status,
        "candidate_config": run.candidate_config,
        "candidate_checksum": run.candidate_checksum,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "requested_by_id": run.requested_by_id,
        "expires_at": run.expires_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "coverage": _coverage(run) if run.candidate_config else None,
        "diff": validation_run_diff(run),
        "regions": regions,
        **_region_counts(run),
    }


def import_validation_evidence(
    *, provider_id: str, candidate_checksum: str, requested_by_id: int
) -> dict[str, Any]:
    run = (
        StorageProviderValidationRun.objects.filter(provider_id=provider_id)
        .prefetch_related("region_validations")
        .first()
    )
    if run is None:
        status = "not_run"
    elif run.status in ACTIVE_RUN_STATUSES:
        status = "running"
    elif (
        run.status == StorageProviderValidationRun.Status.CLEANUP_REQUIRED
        or run.region_validations.filter(
            status=StorageProviderRegionValidation.Status.CLEANUP_FAILED
        ).exists()
        or run.region_validations.filter(bucket_name__isnull=False)
        .exclude(bucket_name="")
        .exists()
    ):
        status = "cleanup_required"
    elif run.status == StorageProviderValidationRun.Status.EXPIRED or run.expires_at <= timezone.now():
        status = "expired"
    elif (
        run.status == StorageProviderValidationRun.Status.PASSED
        and run.requested_by_id == requested_by_id
        and run.candidate_checksum == candidate_checksum
        and not run.region_validations.exclude(
            status=StorageProviderRegionValidation.Status.SUCCESS
        ).exists()
    ):
        status = f"passed_{_coverage(run)}"
    elif run.status in {
        StorageProviderValidationRun.Status.VALIDATION_FAILED,
        StorageProviderValidationRun.Status.CANCELLED,
    }:
        status = "failed"
    else:
        status = "stale"
    total_region_count = len((run.candidate_config or {}).get("regions", [])) if run else 0
    return {
        "provider_id": provider_id,
        "status": status,
        "run_id": str(run.id) if run else None,
        "candidate_checksum": candidate_checksum,
        "run_candidate_checksum": run.candidate_checksum if run else None,
        "selected_region_count": run.region_validations.count() if run else 0,
        "total_region_count": total_region_count,
        "expires_at": run.expires_at.isoformat() if run else None,
    }


def cleanup_expired_validation_runs() -> dict[str, int]:
    now = timezone.now()
    retention_cutoff = now - timedelta(seconds=provider_validation_retention_seconds())
    expired = 0
    deleted = 0
    recovered = 0
    for run in StorageProviderValidationRun.objects.all().order_by("provider_id"):
        if run.status == StorageProviderValidationRun.Status.CLEANUP_REQUIRED:
            continue
        if run.status == StorageProviderValidationRun.Status.PASSED and run.expires_at <= now:
            if run.region_validations.filter(bucket_name__isnull=False).exclude(
                bucket_name=""
            ).exists():
                run.status = StorageProviderValidationRun.Status.CLEANUP_REQUIRED
                run.error_code = "EXPIRED_WITH_RESOURCES"
                run.error_message = "Expired validation still has resources to clean up."
            else:
                run.status = StorageProviderValidationRun.Status.EXPIRED
                run.candidate_config = None
                run.candidate_checksum = None
                run.finished_at = now
                delete_validation_credentials(run.id)
            run.save()
            write_validation_run_audit(run, result="expired")
            expired += 1
            continue
        if run.status in SAFE_TERMINAL_STATUSES and run.finished_at and run.finished_at <= retention_cutoff:
            run_id = run.id
            run.delete()
            delete_validation_credentials(run_id)
            deleted += 1
            continue
        stale_cutoff = now - timedelta(minutes=30)
        if run.status in ACTIVE_RUN_STATUSES and run.updated_at <= stale_cutoff:
            if run.status == StorageProviderValidationRun.Status.VALIDATING:
                run.status = StorageProviderValidationRun.Status.CANCELLING
                run.finished_at = None
                run.save(update_fields=["status", "finished_at", "updated_at"])
                task_name = CLEANUP_TASK_NAME
            elif run.status == StorageProviderValidationRun.Status.CANCELLING:
                task_name = CLEANUP_TASK_NAME
            else:
                task_name = VALIDATION_TASK_NAME
            _enqueue(task_name, run.id)
            recovered += 1
    return {"expired": expired, "deleted": deleted, "recovered": recovered}
