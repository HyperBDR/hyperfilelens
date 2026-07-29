"""Asynchronous Source NAS connection and capacity discovery."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.node.models import Node
from apps.source.constants import (
    ConnectionTestStatus,
    ResourceStatus,
    ResourceType,
)
from apps.source.models import SourceResource
from apps.source.services.internal.connection import (
    apply_connection_test_result_if_current,
    run_connection_test,
)

logger = logging.getLogger(__name__)

SOURCE_REMOTE_IO_QUEUE = "source.remote-io"
_PROBE_MAX_RETRIES = 2
_PROBE_STALE_SECONDS = 15 * 60


def _probe_target(
    *,
    resource_id: int,
    probe_token: str,
    expected_bound_node_id: int,
) -> tuple[SourceResource | None, str]:
    resource = SourceResource.all_objects.filter(pk=resource_id).first()
    if resource is None or resource.is_deleted:
        return None, "source_deleted"
    if resource.status in {ResourceStatus.REMOVING, ResourceStatus.REMOVED}:
        return None, "source_removing"
    if resource.resource_type not in ResourceType.REQUIRES_MOUNT:
        return None, "mount_not_required"
    if int(resource.bound_node_id or 0) != int(expected_bound_node_id or 0):
        return None, "proxy_binding_changed"
    if str(resource.connection_probe_token or "") != str(probe_token or ""):
        return None, "source_changed"
    return resource, ""


def run_source_resource_capacity_probe(
    *,
    resource_id: int,
    probe_token: str,
    expected_bound_node_id: int,
) -> dict:
    """Run one probe and discard its result if the source changes meanwhile."""
    resource, skip_reason = _probe_target(
        resource_id=resource_id,
        probe_token=probe_token,
        expected_bound_node_id=expected_bound_node_id,
    )
    if resource is None:
        return {"status": "skipped", "reason": skip_reason}

    node = resource.bound_node
    if node is None or node.status != Node.Status.ONLINE:
        resource, skip_reason = apply_connection_test_result_if_current(
            resource_id=resource_id,
            probe_token=probe_token,
            expected_bound_node_id=expected_bound_node_id,
            require_mount=True,
            result={
                "success": False,
                "message": "Automatic connection test skipped because the Proxy is offline.",
            },
        )
        if resource is None:
            return {"status": "discarded", "reason": skip_reason}
        return {"status": "failed", "reason": "proxy_offline"}

    SourceResource.all_objects.filter(
        pk=resource.id,
        connection_probe_token=probe_token,
    ).update(
        connection_test_status=ConnectionTestStatus.RUNNING,
        updated_at=timezone.now(),
    )

    result = run_connection_test(resource=resource)

    # The remote call may wait for up to 180 seconds. Lock and re-read the row
    # before applying the result so an edit, rebind, or delete wins the race.
    resource, skip_reason = apply_connection_test_result_if_current(
        resource_id=resource_id,
        probe_token=probe_token,
        expected_bound_node_id=expected_bound_node_id,
        require_mount=True,
        result=result,
    )
    if resource is None:
        return {"status": "discarded", "reason": skip_reason}
    return {
        "status": "success" if result.get("success") else "failed",
        "resource_id": resource.id,
        "message": str(result.get("message") or result.get("error") or ""),
    }


def _record_terminal_probe_failure(
    *,
    resource_id: int,
    probe_token: str,
    expected_bound_node_id: int,
    error: Exception,
) -> dict:
    resource, skip_reason = _probe_target(
        resource_id=resource_id,
        probe_token=probe_token,
        expected_bound_node_id=expected_bound_node_id,
    )
    if resource is None:
        return {"status": "discarded", "reason": skip_reason}
    message = "Automatic Source NAS connection test failed. Retry Test Connection."
    resource, skip_reason = apply_connection_test_result_if_current(
        resource_id=resource_id,
        probe_token=probe_token,
        expected_bound_node_id=expected_bound_node_id,
        require_mount=True,
        result={"success": False, "message": message},
    )
    if resource is None:
        return {"status": "discarded", "reason": skip_reason}
    logger.error(
        "source capacity probe exhausted retries resource_id=%s error=%s",
        resource_id,
        error,
    )
    return {
        "status": "failed",
        "resource_id": resource_id,
        "message": message,
    }


@shared_task(
    name="apps.source.tasks.connection_probe.probe_source_resource_capacity",
    bind=True,
    max_retries=_PROBE_MAX_RETRIES,
)
def probe_source_resource_capacity(
    self,
    *,
    resource_id: int,
    probe_token: str,
    expected_bound_node_id: int,
) -> dict:
    """Run a Source NAS probe without holding up the create API request."""
    try:
        return run_source_resource_capacity_probe(
            resource_id=int(resource_id),
            probe_token=str(probe_token),
            expected_bound_node_id=int(expected_bound_node_id or 0),
        )
    except Exception as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        if retries < _PROBE_MAX_RETRIES:
            raise self.retry(exc=exc, countdown=5 * (2**retries))
        return _record_terminal_probe_failure(
            resource_id=int(resource_id),
            probe_token=str(probe_token),
            expected_bound_node_id=int(expected_bound_node_id or 0),
            error=exc,
        )


def queue_source_resource_capacity_probe(
    *,
    resource_id: int,
    probe_token: str,
    expected_bound_node_id: int,
) -> bool:
    """Best-effort enqueue that cannot turn a committed create into an API 500."""
    try:
        probe_source_resource_capacity.apply_async(
            kwargs={
                "resource_id": int(resource_id),
                "probe_token": str(probe_token),
                "expected_bound_node_id": int(expected_bound_node_id or 0),
            },
            queue=SOURCE_REMOTE_IO_QUEUE,
        )
    except Exception:
        logger.exception(
            "source capacity probe enqueue failed resource_id=%s",
            resource_id,
        )
        SourceResource.all_objects.filter(
            pk=resource_id,
            is_deleted=False,
            connection_probe_token=probe_token,
        ).update(
            connection_test_status=ConnectionTestStatus.FAILED,
            connection_probe_token=None,
            status=ResourceStatus.ERROR,
            status_message=(
                "Automatic connection test could not be queued. Retry Test Connection."
            ),
            connection_test_result=(
                "Automatic connection test could not be queued. Retry Test Connection."
            ),
            updated_at=timezone.now(),
        )
        return False
    return True


def reconcile_stale_source_connection_probes(*, limit: int = 100) -> dict[str, int]:
    """Fail probes that can no longer be owned by a live Celery execution."""
    cutoff = timezone.now() - timedelta(seconds=_PROBE_STALE_SECONDS)
    stale_ids = list(
        SourceResource.all_objects.filter(
            is_deleted=False,
            connection_test_status__in=ConnectionTestStatus.ACTIVE,
            updated_at__lt=cutoff,
        )
        .order_by("updated_at", "id")
        .values_list("id", flat=True)[: max(1, int(limit))]
    )
    if not stale_ids:
        return {"stale": 0, "failed": 0}
    message = "Automatic connection test timed out. Retry Test Connection."
    failed = SourceResource.all_objects.filter(
        id__in=stale_ids,
        is_deleted=False,
        connection_test_status__in=ConnectionTestStatus.ACTIVE,
        updated_at__lt=cutoff,
    ).update(
        connection_test_status=ConnectionTestStatus.FAILED,
        connection_probe_token=None,
        status=ResourceStatus.ERROR,
        status_message=message,
        connection_test_result=message,
        updated_at=timezone.now(),
    )
    if failed:
        logger.warning("reconciled stale source capacity probes count=%s", failed)
    return {"stale": len(stale_ids), "failed": int(failed)}


@shared_task(
    name=(
        "apps.source.tasks.connection_probe."
        "reconcile_stale_source_connection_probes_task"
    )
)
def reconcile_stale_source_connection_probes_task(*, limit: int = 100) -> dict[str, int]:
    return reconcile_stale_source_connection_probes(limit=int(limit))


__all__ = [
    "probe_source_resource_capacity",
    "queue_source_resource_capacity_probe",
    "reconcile_stale_source_connection_probes",
    "reconcile_stale_source_connection_probes_task",
    "run_source_resource_capacity_probe",
]
