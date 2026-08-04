"""Measure the Pipeline-backed Backup Wizard source query on existing data."""

from __future__ import annotations

import statistics
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.source.constants import PipelineStep
from apps.source.models import SourceBackupPipelineEntry
from apps.source.services.internal.backup_selectable import (
    _list_pipeline_backup_selectable_sources,
    _pipeline_queryset,
)


class Command(BaseCommand):
    help = "Benchmark and EXPLAIN the Pipeline-backed Backup Wizard source query without modifying data."

    def add_arguments(self, parser):
        parser.add_argument("--organization-id", type=int, required=True)
        parser.add_argument("--iterations", type=int, default=5)
        parser.add_argument("--page-size", type=int, default=100)
        parser.add_argument("--minimum-sources", type=int, default=10_000)

    def handle(self, *args, **options):
        organization_id = int(options["organization_id"])
        iterations = max(1, int(options["iterations"]))
        page_size = max(1, min(100, int(options["page_size"])))
        minimum_sources = max(1, int(options["minimum_sources"]))
        source_count = SourceBackupPipelineEntry.objects.filter(
            organization_id=organization_id,
            is_deleted=False,
        ).count()
        if source_count < minimum_sources:
            raise CommandError(
                f"Organization {organization_id} has {source_count} Pipeline sources; "
                f"at least {minimum_sources} are required."
            )

        durations_ms: list[float] = []
        query_counts: list[int] = []
        filters = {
            "search": None,
            "search_field": None,
            "source_name": None,
            "source_hostname": None,
            "source_ip": None,
            "status": None,
            "source_status": None,
            "availability": None,
            "source_type": None,
            "exclude_ids": None,
            "pipeline_step": PipelineStep.READY,
            "running_task": None,
            "backup_running": None,
            "restore_running": None,
            "backup_policy_id": None,
            "file_filter_rule_id": None,
            "repository_id": None,
        }
        for _index in range(iterations):
            query_count = 0

            def count_query(execute, sql, params, many, context):
                nonlocal query_count
                query_count += 1
                return execute(sql, params, many, context)

            started = time.perf_counter()
            with connection.execute_wrapper(count_query):
                _list_pipeline_backup_selectable_sources(
                    organization_id=organization_id,
                    page=1,
                    page_size=page_size,
                    expand=None,
                    **filters,
                )
            durations_ms.append((time.perf_counter() - started) * 1000)
            query_counts.append(query_count)

        queryset = _pipeline_queryset(organization_id=organization_id, **filters)
        sorted_durations = sorted(durations_ms)
        p95_index = max(0, min(len(sorted_durations) - 1, round(0.95 * len(sorted_durations)) - 1))
        self.stdout.write(
            " ".join(
                (
                    f"sources={source_count}",
                    f"iterations={iterations}",
                    f"page_size={page_size}",
                    f"query_count_max={max(query_counts)}",
                    f"latency_ms_avg={statistics.fmean(durations_ms):.2f}",
                    f"latency_ms_p95={sorted_durations[p95_index]:.2f}",
                )
            )
        )
        self.stdout.write(queryset.explain(analyze=True, buffers=True, verbose=True))
