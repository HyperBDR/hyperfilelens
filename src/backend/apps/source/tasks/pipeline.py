"""Periodic repair for the source backup Pipeline read model."""

from celery import shared_task

from apps.source.services.internal.source_pipeline import reconcile_pipeline_projections


@shared_task(name="apps.source.tasks.pipeline.reconcile_source_pipeline_task")
def reconcile_source_pipeline_task(*, limit: int = 100) -> dict[str, int]:
    return reconcile_pipeline_projections(limit=max(1, int(limit)))
