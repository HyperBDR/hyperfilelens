from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.node.models import NodeTask
from apps.protection.models import BackupSourceSnapshot, BackupSourceSnapshotDirectory
from apps.protection.services.kopia_snapshot_delete import classify_kopia_snapshot_delete_results
from apps.task.models import Task, TaskResource
from apps.task.services.interface import complete_task


class Command(BaseCommand):
    help = "Reconcile snapshot delete tasks and logical snapshots after legacy non-idempotent deletes."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Apply changes; default is dry-run.")
        parser.add_argument("--source-type")
        parser.add_argument("--source-ref-id", type=int)

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        snapshots = BackupSourceSnapshot.objects.exclude(status=BackupSourceSnapshot.Status.DELETED)
        if options.get("source_type"):
            snapshots = snapshots.filter(source_type=options["source_type"])
        if options.get("source_ref_id") is not None:
            snapshots = snapshots.filter(source_ref_id=options["source_ref_id"])

        reconciled = 0
        delete_failed = 0
        unchanged = 0
        for snapshot in snapshots.iterator():
            task = (
                Task.objects.filter(
                    organization_id=snapshot.organization_id,
                    task_type=Task.Type.SNAPSHOT_DELETE,
                    resources__resource_type=TaskResource.Type.SNAPSHOT,
                    resources__resource_id=snapshot.id,
                )
                .order_by("-created_at", "-id")
                .first()
            )
            if task is None:
                unchanged += 1
                continue
            result = task.result_payload if isinstance(task.result_payload, dict) else {}
            if not result.get("results"):
                node_task = NodeTask.objects.filter(
                    organization_id=snapshot.organization_id,
                    correlation_type="protection.snapshot_delete",
                    correlation_id=str(task.task_uuid),
                ).order_by("-created_at").first()
                if node_task is not None and isinstance(node_task.result, dict):
                    result = node_task.result
            items = result.get("results") if isinstance(result.get("results"), list) else []
            deleted_ids, absent_ids, hard_failures = classify_kopia_snapshot_delete_results(
                [item for item in items if isinstance(item, dict)]
            )
            reconciled_ids = deleted_ids | absent_ids
            directory_ids = set(
                BackupSourceSnapshotDirectory.objects.filter(source_snapshot=snapshot)
                .exclude(status=BackupSourceSnapshotDirectory.Status.DELETED)
                .exclude(kopia_snapshot_id__isnull=True)
                .exclude(kopia_snapshot_id="")
                .values_list("kopia_snapshot_id", flat=True)
            )
            can_finalize = bool(items) and not hard_failures and directory_ids.issubset(reconciled_ids)
            target = "deleted" if can_finalize else "delete_failed"
            self.stdout.write(
                f"snapshot={snapshot.id} task={task.task_uuid} current={snapshot.status} target={target} "
                f"reconciled_ids={len(reconciled_ids)} hard_failures={len(hard_failures)}"
            )
            if not apply_changes:
                reconciled += int(can_finalize)
                delete_failed += int(not can_finalize)
                continue
            with transaction.atomic():
                if reconciled_ids:
                    BackupSourceSnapshotDirectory.objects.filter(
                        source_snapshot=snapshot,
                        kopia_snapshot_id__in=reconciled_ids,
                    ).update(status=BackupSourceSnapshotDirectory.Status.DELETED, updated_at=timezone.now())
                if can_finalize:
                    snapshot.status = BackupSourceSnapshot.Status.DELETED
                    snapshot.deleted_at = timezone.now()
                    snapshot.error_code = ""
                    snapshot.error_message = ""
                    snapshot.save(update_fields=["status", "deleted_at", "error_code", "error_message", "updated_at"])
                    if task.status not in {Task.Status.SUCCESS, Task.Status.CANCELLED, Task.Status.TIMEOUT}:
                        complete_task(
                            task_uuid=task.task_uuid,
                            organization_id=task.organization_id,
                            status=Task.Status.SUCCESS,
                            progress=100,
                            result_payload=result,
                        )
                    reconciled += 1
                else:
                    snapshot.status = BackupSourceSnapshot.Status.DELETE_FAILED
                    snapshot.error_code = "SNAPSHOT_DELETE_REPAIR_REQUIRED"
                    snapshot.error_message = task.error_message or "Snapshot delete requires retry."
                    snapshot.save(update_fields=["status", "error_code", "error_message", "updated_at"])
                    delete_failed += 1

        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: reconciled={reconciled} delete_failed={delete_failed} unchanged={unchanged}"
        ))
