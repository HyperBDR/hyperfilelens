"""Persist Source availability observations and project Node availability."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.source.constants import Availability, ResourceType
from apps.source.models import SourceResource


RESULT_OBSERVATION_KEY = "_availability_observation"


def result_with_availability_observation(
    result: dict[str, Any],
    availability: str,
) -> dict[str, Any]:
    """Attach an internal observation marker without changing public API fields."""
    return {**result, RESULT_OBSERVATION_KEY: availability}


def public_connection_result(result: dict[str, Any]) -> dict[str, Any]:
    """Remove internal observation metadata from an API response."""
    return {
        key: value
        for key, value in result.items()
        if key != RESULT_OBSERVATION_KEY
    }


def confirmed_agent_failure(outcome: Any) -> bool:
    """Return whether an Agent accepted a NAS task and reported its failure."""
    if bool(getattr(outcome, "timed_out", False)):
        return False
    task = getattr(outcome, "task", None)
    return bool(
        task is not None
        and str(getattr(task, "status", "") or "").lower() == "failed"
        and getattr(task, "accepted_at", None) is not None
    )


def apply_result_availability(
    *,
    resource: SourceResource,
    result: dict[str, Any],
    observed_at: datetime | None = None,
) -> bool:
    """Apply only a conclusive NAS observation to a current locked resource."""
    observation = str(result.get(RESULT_OBSERVATION_KEY) or "").lower()
    if result.get("success"):
        observation = Availability.ONLINE
    if observation not in {Availability.ONLINE, Availability.OFFLINE}:
        return False
    if (
        observation == Availability.ONLINE
        and (
            resource.bound_node is None
            or resource.bound_node.availability != Node.Availability.ONLINE
        )
    ):
        return False
    resource.availability = observation
    resource.availability_updated_at = observed_at or timezone.now()
    return True


def record_mount_availability(
    *,
    resource: SourceResource,
    availability: str,
    observed_at: datetime | None = None,
) -> None:
    """Persist a conclusive mount observation without changing legacy fields."""
    if availability not in {Availability.ONLINE, Availability.OFFLINE}:
        raise ValueError("invalid source availability")
    if (
        availability == Availability.ONLINE
        and (
            resource.bound_node is None
            or resource.bound_node.availability != Node.Availability.ONLINE
        )
    ):
        return
    resource.availability = availability
    resource.availability_updated_at = observed_at or timezone.now()


def project_node_availability(
    *,
    node_id: int,
    transitioned: bool,
) -> None:
    """Mirror Agent availability and apply Proxy transitions to bound sources."""
    node = Node.objects.filter(pk=node_id, is_deleted=False).first()
    if node is None:
        return

    if node.role == NodeRole.AGENT:
        SourceResource.objects.filter(
            bound_node_id=node.id,
            resource_type=ResourceType.LOCAL,
            is_deleted=False,
        ).update(
            availability=node.availability,
            availability_updated_at=node.availability_updated_at,
        )
        from apps.source.constants import SelectableSourceKind
        from apps.source.services.internal.source_pipeline import sync_pipeline_projection

        sync_pipeline_projection(
            organization_id=node.organization_id,
            source_kind=SelectableSourceKind.AGENT,
            ref_id=node.id,
        )
        return

    if node.role != NodeRole.PROXY:
        return
    if node.availability == Node.Availability.OFFLINE:
        SourceResource.objects.filter(
            bound_node_id=node.id,
            resource_type__in=ResourceType.REQUIRES_MOUNT,
            is_deleted=False,
        ).update(
            availability=Availability.OFFLINE,
            availability_updated_at=node.availability_updated_at,
        )
        from apps.source.services.internal.source_pipeline import sync_bound_proxy_pipeline_projections

        sync_bound_proxy_pipeline_projections(proxy_id=node.id)
        return
    if not transitioned:
        return

    from apps.source.tasks.connection_probe import (
        SOURCE_REMOTE_IO_QUEUE,
        queue_source_availability_probes_for_proxy_task,
    )

    transaction.on_commit(
        lambda: queue_source_availability_probes_for_proxy_task.apply_async(
            kwargs={"proxy_id": node.id},
            queue=SOURCE_REMOTE_IO_QUEUE,
        )
    )
    from apps.source.services.internal.source_pipeline import sync_bound_proxy_pipeline_projections

    sync_bound_proxy_pipeline_projections(proxy_id=node.id)
