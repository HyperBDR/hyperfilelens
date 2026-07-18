from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.protection.models import BackupConfig, BackupPolicy, BackupSourceSnapshot
from apps.protection.services.backup_task import start_backup_tasks
from apps.protection.services.snapshot_delete import create_and_queue_snapshot_delete_task
from apps.task.models import Task


@dataclass(frozen=True)
class PolicyExecutionSummary:
    scheduled: int = 0
    retention_tasks: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "scheduled": self.scheduled,
            "retention_tasks": self.retention_tasks,
            "skipped": self.skipped,
        }


def _cron_value_matches(field: str, value: int) -> bool:
    field = str(field or "").strip()
    if field == "*":
        return True
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        base = part
        if "/" in part:
            base, raw_step = part.split("/", 1)
            try:
                step = max(1, int(raw_step))
            except (TypeError, ValueError):
                return False
        if base == "*":
            return value % step == 0
        if "-" in base:
            start_raw, end_raw = base.split("-", 1)
            try:
                start = int(start_raw)
                end = int(end_raw)
            except (TypeError, ValueError):
                return False
            if start <= value <= end and (value - start) % step == 0:
                return True
            continue
        try:
            if int(base) == value:
                return True
        except (TypeError, ValueError):
            return False
    return False


def cron_matches_now(cron_expr: str, *, now=None) -> bool:
    current = timezone.localtime(now or timezone.now()).replace(second=0, microsecond=0)
    fields = str(cron_expr or "").split()
    if len(fields) != 5:
        return False
    minute, hour, day_of_month, month, day_of_week = fields
    # Python weekday: Monday=0; cron commonly accepts Sunday=0. This maps Sunday to 0.
    cron_weekday = 0 if current.weekday() == 6 else current.weekday() + 1
    weekday_matches = _cron_value_matches(day_of_week, cron_weekday) or (
        cron_weekday == 0 and _cron_value_matches(day_of_week, 7)
    )
    return (
        _cron_value_matches(minute, current.minute)
        and _cron_value_matches(hour, current.hour)
        and _cron_value_matches(day_of_month, current.day)
        and _cron_value_matches(month, current.month)
        and weekday_matches
    )


def _policy_configs() -> list[tuple[BackupConfig, BackupPolicy]]:
    configs = list(
        BackupConfig.objects.exclude(backup_policy_id__isnull=True)
        .exclude(backup_policy_id=0)
        .order_by("organization_id", "id")
    )
    policy_ids = {int(config.backup_policy_id) for config in configs if config.backup_policy_id}
    policies = {
        int(policy.id): policy
        for policy in BackupPolicy.objects.filter(id__in=policy_ids, is_active=True)
    }
    return [
        (config, policies[int(config.backup_policy_id)])
        for config in configs
        if config.backup_policy_id and int(config.backup_policy_id) in policies
    ]


def schedule_due_backup_tasks(*, now=None) -> dict[str, int]:
    current = timezone.localtime(now or timezone.now()).replace(second=0, microsecond=0)
    scheduled = 0
    skipped = 0
    for config, policy in _policy_configs():
        schedule = policy.schedule if isinstance(policy.schedule, dict) else {}
        if not schedule.get("enabled", False):
            skipped += 1
            continue
        if not cron_matches_now(str(schedule.get("cron_expr") or ""), now=current):
            skipped += 1
            continue
        fire_key = current.strftime("%Y%m%d%H%M")
        result = start_backup_tasks(
            organization_id=config.organization_id,
            sources=[
                {
                    "source_type": config.source_type,
                    "source_ref_id": config.source_ref_id,
                }
            ],
            backup_config_ids=[config.id],
            trigger_type=BackupSourceSnapshot.TriggerType.SCHEDULE,
            idempotency_key=f"schedule:{policy.id}:{config.id}:{fire_key}",
        )
        scheduled += int(result.get("created_count") or 0)
        skipped += int(result.get("skipped_count") or 0)
    return {"scheduled": scheduled, "skipped": skipped}


def _snapshot_time(snapshot: BackupSourceSnapshot):
    return snapshot.finished_at or snapshot.started_at or snapshot.created_at


def _bucket_key(snapshot: BackupSourceSnapshot, unit: str):
    value = timezone.localtime(_snapshot_time(snapshot))
    if unit == "hour":
        return value.strftime("%Y%m%d%H")
    if unit == "day":
        return value.strftime("%Y%m%d")
    if unit == "week":
        iso = value.isocalendar()
        return f"{iso.year}W{iso.week:02d}"
    if unit == "month":
        return value.strftime("%Y%m")
    if unit == "year":
        return value.strftime("%Y")
    return str(snapshot.id)


def _apply_bucket_retention(
    *,
    keep_ids: set[int],
    snapshots: list[BackupSourceSnapshot],
    now,
    enabled: bool,
    amount: int,
    unit: str,
    delta: timedelta,
) -> None:
    if not enabled or amount < 1:
        return
    cutoff = now - delta
    seen: set[str] = set()
    for snapshot in snapshots:
        if _snapshot_time(snapshot) < cutoff:
            continue
        key = _bucket_key(snapshot, unit)
        if key in seen:
            continue
        seen.add(key)
        keep_ids.add(int(snapshot.id))


def retention_delete_candidates_for_config(
    *,
    config: BackupConfig,
    policy: BackupPolicy,
    now=None,
) -> list[BackupSourceSnapshot]:
    retention = policy.retention if isinstance(policy.retention, dict) else {}
    if not retention.get("enabled", False):
        return []
    snapshots = list(
        BackupSourceSnapshot.objects.filter(
            organization_id=config.organization_id,
            source_type=config.source_type,
            source_ref_id=config.source_ref_id,
            backup_config_id=config.id,
            deleted_at__isnull=True,
            status__in=[
                BackupSourceSnapshot.Status.AVAILABLE,
                BackupSourceSnapshot.Status.PARTIAL,
            ],
        ).order_by("-finished_at", "-created_at", "-id")
    )
    if len(snapshots) <= 1:
        return []
    current = timezone.localtime(now or timezone.now())
    keep_ids = {int(snapshot.id) for snapshot in snapshots[: max(1, int(retention.get("recent_points") or 1))]}
    _apply_bucket_retention(
        keep_ids=keep_ids,
        snapshots=snapshots,
        now=current,
        enabled=bool(retention.get("hourly_enabled", False)),
        amount=int(retention.get("hourly_hours") or 0),
        unit="hour",
        delta=timedelta(hours=max(1, int(retention.get("hourly_hours") or 1))),
    )
    _apply_bucket_retention(
        keep_ids=keep_ids,
        snapshots=snapshots,
        now=current,
        enabled=bool(retention.get("daily_enabled", False)),
        amount=int(retention.get("daily_days") or 0),
        unit="day",
        delta=timedelta(days=max(1, int(retention.get("daily_days") or 1))),
    )
    _apply_bucket_retention(
        keep_ids=keep_ids,
        snapshots=snapshots,
        now=current,
        enabled=bool(retention.get("weekly_enabled", False)),
        amount=int(retention.get("weekly_weeks") or 0),
        unit="week",
        delta=timedelta(weeks=max(1, int(retention.get("weekly_weeks") or 1))),
    )
    _apply_bucket_retention(
        keep_ids=keep_ids,
        snapshots=snapshots,
        now=current,
        enabled=bool(retention.get("monthly_enabled", False)),
        amount=int(retention.get("monthly_months") or 0),
        unit="month",
        delta=timedelta(days=31 * max(1, int(retention.get("monthly_months") or 1))),
    )
    _apply_bucket_retention(
        keep_ids=keep_ids,
        snapshots=snapshots,
        now=current,
        enabled=bool(retention.get("annual_enabled", False)),
        amount=int(retention.get("annual_years") or 0),
        unit="year",
        delta=timedelta(days=366 * max(1, int(retention.get("annual_years") or 1))),
    )
    return [snapshot for snapshot in snapshots if int(snapshot.id) not in keep_ids]


def apply_retention_policies(*, now=None, limit: int = 100) -> dict[str, int]:
    created = 0
    skipped = 0
    for config, policy in _policy_configs():
        for snapshot in retention_delete_candidates_for_config(
            config=config,
            policy=policy,
            now=now,
        )[: max(1, int(limit))]:
            with transaction.atomic():
                task = create_and_queue_snapshot_delete_task(
                    source_snapshot=snapshot,
                    trigger_type=Task.TriggerType.SYSTEM,
                )
            if task.status in {Task.Status.PENDING, Task.Status.RUNNING}:
                created += 1
            else:
                skipped += 1
    return {"retention_tasks": created, "skipped": skipped}


def run_backup_policy_maintenance(*, now=None, retention_limit: int = 100) -> dict[str, int]:
    scheduled = schedule_due_backup_tasks(now=now)
    retention = apply_retention_policies(now=now, limit=retention_limit)
    return {
        "scheduled": int(scheduled.get("scheduled") or 0),
        "retention_tasks": int(retention.get("retention_tasks") or 0),
        "skipped": int(scheduled.get("skipped") or 0) + int(retention.get("skipped") or 0),
    }
