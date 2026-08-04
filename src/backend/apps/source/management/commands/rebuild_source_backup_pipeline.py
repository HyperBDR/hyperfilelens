"""Rebuild the Source backup Pipeline read model."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.node.models import Node
from apps.node.models.base import NodeRole
from apps.source.constants import ResourceType, SelectableSourceKind
from apps.source.models import SourceBackupPipelineEntry, SourceResource
from apps.source.services.internal.source_pipeline import _source_and_tasks, ensure_pipeline_entry
from apps.source.services.internal.source_pipeline_projection import build_source_projection


class Command(BaseCommand):
    help = "Rebuild source_backup_pipeline. Defaults to a read-only dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--organization-id", type=int)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--apply", action="store_true", help="Apply repairs; default is dry-run.")

    def handle(self, *args, **options):
        batch_size = int(options["batch_size"])
        if not 1 <= batch_size <= 5000:
            raise CommandError("--batch-size must be between 1 and 5000")
        organization_id = options.get("organization_id")
        apply_changes = bool(options["apply"])
        stats = {key: 0 for key in (
            "scanned_sources", "scanned_rows", "missing", "revived", "field_mismatches",
            "created_at_mismatches", "stale", "nas_without_proxy", "created", "updated",
            "quarantined", "unchanged",
        )}
        active_keys = set()

        agents = Node.objects.filter(role=NodeRole.AGENT)
        nas = SourceResource.objects.filter(resource_type=ResourceType.NAS).select_related("bound_node")
        if organization_id is not None:
            agents = agents.filter(organization_id=organization_id)
            nas = nas.filter(organization_id=organization_id)
        for kind, queryset in ((SelectableSourceKind.AGENT, agents), (SelectableSourceKind.NAS, nas)):
            for source in queryset.iterator(chunk_size=batch_size):
                stats["scanned_sources"] += 1
                key = (source.organization_id, kind, source.id)
                active_keys.add(key)
                row = SourceBackupPipelineEntry.all_objects.filter(
                    organization_id=source.organization_id, source_kind=kind, ref_id=source.id
                ).first()
                was_missing = row is None
                was_deleted = bool(row and row.is_deleted)
                _current_source, backup_task, restore_task = _source_and_tasks(
                    organization_id=source.organization_id,
                    source_kind=kind,
                    ref_id=source.id,
                )
                if kind == SelectableSourceKind.NAS:
                    values, inconsistency = build_source_projection(
                        source_kind=kind,
                        source=source,
                        backup_task=backup_task,
                        restore_task=restore_task,
                    )
                    stats["nas_without_proxy"] += int(inconsistency == "nas_without_proxy")
                else:
                    values, _ = build_source_projection(
                        source_kind=kind,
                        source=source,
                        backup_task=backup_task,
                        restore_task=restore_task,
                    )
                mismatched = row is None or any(getattr(row, field) != value for field, value in values.items())
                created_at_mismatch = row is None or row.created_at != source.created_at
                if was_missing:
                    stats["missing"] += 1
                if was_deleted:
                    stats["revived"] += 1
                if mismatched and not was_missing:
                    stats["field_mismatches"] += 1
                if created_at_mismatch and not was_missing:
                    stats["created_at_mismatches"] += 1
                if not (was_missing or was_deleted or mismatched or created_at_mismatch):
                    stats["unchanged"] += 1
                    continue
                if not apply_changes:
                    continue
                with transaction.atomic():
                    entry = ensure_pipeline_entry(
                        organization_id=source.organization_id, source_kind=kind, ref_id=source.id
                    )
                    if entry is None:
                        continue
                    if was_missing:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                    if entry.created_at != source.created_at:
                        SourceBackupPipelineEntry.all_objects.filter(pk=entry.pk).update(created_at=source.created_at)

        rows = SourceBackupPipelineEntry.objects.all()
        if organization_id is not None:
            rows = rows.filter(organization_id=organization_id)
        for row in rows.iterator(chunk_size=batch_size):
            stats["scanned_rows"] += 1
            if (row.organization_id, row.source_kind, row.ref_id) in active_keys:
                continue
            stats["stale"] += 1
            if apply_changes:
                row.soft_delete()
                stats["quarantined"] += 1

        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write("{}: {}".format(mode, " ".join(f"{key}={value}" for key, value in stats.items())))
