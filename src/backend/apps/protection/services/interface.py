from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.protection.models import BackupConfig, BackupPolicy, FileFilterRule

CRON_FIELD_RE = re.compile(r"^(\*|\d+(-\d+)?)(/\d+)?(,(\*|\d+(-\d+)?)(/\d+)?)*$")


class ResourceInUseError(Exception):
    pass


@dataclass(frozen=True)
class BulkFailure:
    id: int
    reason: str


def normalize_ignore_patterns(raw: str | None) -> str:
    lines = [line.strip() for line in str(raw or "").splitlines()]
    return "\n".join(line for line in lines if line)


def validate_cron_expr(raw: str) -> str:
    cron_expr = str(raw or "").strip()
    if not cron_expr:
        raise ValidationError({"schedule": "cron_expr is required."})
    fields = cron_expr.split()
    if len(fields) != 5 or any(not CRON_FIELD_RE.match(field) for field in fields):
        raise ValidationError({"schedule": "cron_expr must be a valid 5-field cron expression."})
    return cron_expr


def _bool(data: dict[str, Any], key: str, default: bool = False) -> bool:
    value = data.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int(data: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(data.get(key, default) or default)
    except (TypeError, ValueError) as exc:
        raise ValidationError({key: f"{key} must be an integer."}) from exc


def normalize_schedule(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError({"schedule": "schedule must be an object."})
    enabled = _bool(value, "enabled", True)
    cron_expr = validate_cron_expr(str(value.get("cron_expr") or ""))
    return {"enabled": enabled, "cron_expr": cron_expr}


def _coerce_retention_input(value: dict[str, Any]) -> dict[str, Any]:
    if "hourly_enabled" in value or "hourly_hours" in value or "hourly_days" in value:
        return value
    migrated = dict(value)
    if "short_hourly_enabled" in value:
        migrated.setdefault("hourly_enabled", value.get("short_hourly_enabled", True))
        short_days = _int(value, "short_days", 2)
        migrated.setdefault("hourly_hours", short_days * 24)
    if "mid_daily_enabled" in value:
        migrated.setdefault("daily_enabled", value.get("mid_daily_enabled", True))
        migrated.setdefault("daily_days", value.get("mid_days", 30))
    if "long_monthly_enabled" in value:
        migrated.setdefault("monthly_enabled", value.get("long_monthly_enabled", True))
        migrated.setdefault("monthly_months", value.get("long_months", 12))
    migrated.setdefault("weekly_enabled", False)
    migrated.setdefault("weekly_weeks", 4)
    migrated.setdefault("annual_enabled", False)
    migrated.setdefault("annual_years", 5)
    return migrated


def _resolve_hourly_hours(value: dict[str, Any]) -> int:
    if "hourly_hours" in value:
        return _int(value, "hourly_hours")
    if "hourly_days" in value:
        return _int(value, "hourly_days") * 24
    return 48


def normalize_retention(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError({"retention": "retention must be an object."})
    value = _coerce_retention_input(value)
    enabled = _bool(value, "enabled", True)
    recent_points = _int(value, "recent_points")
    hourly_hours = _resolve_hourly_hours(value)
    daily_days = _int(value, "daily_days")
    weekly_weeks = _int(value, "weekly_weeks")
    monthly_months = _int(value, "monthly_months")
    annual_years = _int(value, "annual_years")
    hourly_enabled = _bool(value, "hourly_enabled", True)
    daily_enabled = _bool(value, "daily_enabled", True)
    weekly_enabled = _bool(value, "weekly_enabled", True)
    monthly_enabled = _bool(value, "monthly_enabled", True)
    annual_enabled = _bool(value, "annual_enabled", True)
    if recent_points < 1:
        raise ValidationError({"retention": "recent_points must be at least 1."})
    if hourly_enabled and hourly_hours < 1:
        raise ValidationError({"retention": "hourly_hours must be at least 1 when hourly retention is enabled."})
    if daily_enabled and daily_days < 1:
        raise ValidationError({"retention": "daily_days must be at least 1 when daily retention is enabled."})
    if weekly_enabled and weekly_weeks < 1:
        raise ValidationError({"retention": "weekly_weeks must be at least 1 when weekly retention is enabled."})
    if monthly_enabled and monthly_months < 1:
        raise ValidationError({"retention": "monthly_months must be at least 1 when monthly retention is enabled."})
    if annual_enabled and annual_years < 1:
        raise ValidationError({"retention": "annual_years must be at least 1 when annual retention is enabled."})
    if not 1 <= hourly_hours <= 87600:
        raise ValidationError({"retention": "hourly_hours must be between 1 and 87600."})
    if not 1 <= daily_days <= 3650:
        raise ValidationError({"retention": "daily_days must be between 1 and 3650."})
    if not 1 <= weekly_weeks <= 520:
        raise ValidationError({"retention": "weekly_weeks must be between 1 and 520."})
    if not 1 <= monthly_months <= 120:
        raise ValidationError({"retention": "monthly_months must be between 1 and 120."})
    if not 1 <= annual_years <= 100:
        raise ValidationError({"retention": "annual_years must be between 1 and 100."})
    return {
        "enabled": enabled,
        "recent_points": recent_points,
        "hourly_enabled": hourly_enabled,
        "hourly_hours": hourly_hours,
        "daily_enabled": daily_enabled,
        "daily_days": daily_days,
        "weekly_enabled": weekly_enabled,
        "weekly_weeks": weekly_weeks,
        "monthly_enabled": monthly_enabled,
        "monthly_months": monthly_months,
        "annual_enabled": annual_enabled,
        "annual_years": annual_years,
    }


def normalize_throttling(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError({"throttling": "throttling must be an object."})
    enabled = _bool(value, "enabled", False)
    unlimited = _bool(value, "unlimited", True)
    rate_mbps = _int(value, "rate_mbps")
    if enabled and not unlimited and rate_mbps <= 0:
        raise ValidationError({"throttling": "rate_mbps must be greater than 0."})
    return {
        "enabled": enabled,
        "unlimited": unlimited,
        "rate_mbps": rate_mbps,
    }


def normalize_error_handling(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError({"error_handling": "error_handling must be an object."})
    return {
        "enabled": _bool(value, "enabled", False),
        "ignore_directory_read_errors": _bool(value, "ignore_directory_read_errors", True),
        "ignore_file_read_errors": _bool(value, "ignore_file_read_errors", False),
        "ignore_unknown_entries": _bool(value, "ignore_unknown_entries", True),
    }


def _humanize_cron_expression(expr: str) -> str:
    cron_expr = str(expr or "").strip()
    if not cron_expr:
        return "Not set"
    parts = cron_expr.split()
    if len(parts) != 5:
        return "Custom schedule"

    minute, hour, dom, month, dow = parts

    def is_star(field: str) -> bool:
        return field == "*"

    minute_step = re.fullmatch(r"\*/(\d+)", minute)
    if minute_step and is_star(hour) and is_star(dom) and is_star(month) and is_star(dow):
        n = int(minute_step.group(1))
        suffix = "" if n == 1 else "s"
        return f"Every {n} minute{suffix}"

    hour_step = re.fullmatch(r"\*/(\d+)", hour)
    if minute in {"0", "00"} and hour_step and is_star(dom) and is_star(month) and is_star(dow):
        n = int(hour_step.group(1))
        suffix = "" if n == 1 else "s"
        return f"Every {n} hour{suffix}"

    dom_step = re.fullmatch(r"\*/(\d+)", dom)
    if minute in {"0", "00"} and hour in {"0", "00"} and dom_step and is_star(month) and is_star(dow):
        n = int(dom_step.group(1))
        suffix = "" if n == 1 else "s"
        return f"Every {n} day{suffix}"

    if minute.isdigit() and hour.isdigit() and is_star(dom) and is_star(month) and is_star(dow):
        return f"Daily at {int(hour):02d}:{int(minute):02d}"

    if minute.isdigit() and is_star(hour) and is_star(dom) and is_star(month) and is_star(dow):
        return f"At minute {int(minute)} of every hour"

    if minute in {"0", "00"} and hour.isdigit() and is_star(dom) and is_star(month) and dow.isdigit():
        weekday = int(dow)
        if 0 <= weekday <= 6:
            weekday_names = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ]
            return f"Weekly on {weekday_names[weekday]} at {int(hour):02d}:00"

    if minute in {"0", "00"} and hour.isdigit() and dom.isdigit() and is_star(month) and is_star(dow):
        return f"Monthly on day {int(dom)} at {int(hour):02d}:00"

    return "Custom schedule"


def backup_policy_schedule_summary(policy: BackupPolicy) -> str:
    schedule = policy.schedule or {}
    if not schedule.get("enabled", False):
        return "Not configured"
    return _humanize_cron_expression(str(schedule.get("cron_expr") or ""))


def _retention_hourly_hours(retention: dict[str, Any]) -> int:
    if retention.get("hourly_hours") is not None:
        return int(retention.get("hourly_hours") or 0)
    if retention.get("hourly_days") is not None:
        return int(retention.get("hourly_days") or 0) * 24
    return 0


def backup_policy_retention_summary(policy: BackupPolicy) -> str:
    retention = policy.retention or {}
    if not retention.get("enabled", False):
        return "Not configured"
    parts = [f"Latest {retention.get('recent_points', 0)}"]
    if retention.get("hourly_enabled"):
        parts.append(f"H {_retention_hourly_hours(retention)}h")
    if retention.get("daily_enabled"):
        parts.append(f"D {retention.get('daily_days', 0)}d")
    if retention.get("weekly_enabled"):
        parts.append(f"W {retention.get('weekly_weeks', 0)}w")
    if retention.get("monthly_enabled"):
        parts.append(f"M {retention.get('monthly_months', 0)}mo")
    if retention.get("annual_enabled"):
        parts.append(f"Y {retention.get('annual_years', 0)}y")
    return " · ".join(parts)


def _summarize_ignore_patterns(patterns_text: str, *, limit: int | None = None) -> str:
    lines = [
        line.strip()
        for line in str(patterns_text or "").splitlines()
        if line.strip() and not line.strip().startswith("!")
    ]
    if not lines:
        return ""
    exts: list[str] = []
    paths: list[str] = []
    for line in lines:
        if "*." in line:
            exts.append(line[line.index("*.") :])
        else:
            paths.append(line.replace("**/", "").replace("/**", "/"))
    bits: list[str] = []
    if exts:
        ext_text = ", ".join(exts if limit is None else exts[:limit])
        if limit is not None and len(exts) > limit:
            ext_text = f"{ext_text} +{len(exts) - limit}"
        bits.append(ext_text)
    if paths:
        path_limit = limit if limit is not None else len(paths)
        path_text = ", ".join(paths if limit is None else paths[:path_limit])
        if limit is not None and len(paths) > path_limit:
            path_text = f"{path_text} +{len(paths) - path_limit}"
        bits.append(path_text)
    return " · ".join(bits)


def _summarize_exception_patterns(patterns_text: str, *, limit: int | None = None) -> str:
    lines = [
        line.strip()[1:].strip()
        for line in str(patterns_text or "").splitlines()
        if line.strip().startswith("!") and line.strip()[1:].strip()
    ]
    if not lines:
        return ""
    text = ", ".join(lines if limit is None else lines[:limit])
    if limit is not None and len(lines) > limit:
        text = f"{text} +{len(lines) - limit}"
    return text


def _format_large_file_limit(bytes_max: int) -> str:
    if bytes_max >= 1024 * 1024 * 1024 and bytes_max % (1024 * 1024 * 1024) == 0:
        return f">{bytes_max // (1024 * 1024 * 1024)} GB"
    if bytes_max >= 1024 * 1024 and bytes_max % (1024 * 1024) == 0:
        return f">{bytes_max // (1024 * 1024)} MB"
    if bytes_max >= 1024 and bytes_max % 1024 == 0:
        return f">{bytes_max // 1024} KB"
    return f">{bytes_max} B"


def _file_filter_advanced_summary(rule: FileFilterRule) -> str:
    parts: list[str] = []
    if rule.large_file_limit_enabled and rule.large_file_bytes_max > 0:
        parts.append(_format_large_file_limit(int(rule.large_file_bytes_max)))
    else:
        parts.append("No size limit")
    parts.append("Skip cache dirs" if rule.ignore_cache_directories else "Include cache dirs")
    if rule.current_filesystem_only:
        parts.append("Current FS only")
    return " · ".join(parts)


def file_filter_summary(rule: FileFilterRule) -> str:
    pattern_part = _summarize_ignore_patterns(rule.ignore_patterns)
    exception_part = _summarize_exception_patterns(rule.ignore_patterns)
    exclude_value = pattern_part or "None"
    advanced_value = _file_filter_advanced_summary(rule)
    parts = [f"Exclude: {exclude_value}"]
    if exception_part:
        parts.append(f"Exceptions: {exception_part}")
    parts.append(f"Advanced: {advanced_value}")
    return "\n".join(parts)


def _policy_payload(data: dict[str, Any], current: BackupPolicy | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if current is not None:
        merged = {
            "name": current.name,
            "is_active": current.is_active,
            "schedule": current.schedule,
            "retention": current.retention,
            "throttling": current.throttling,
            "error_handling": current.error_handling,
        }
    merged.update(data)
    name = str(merged.get("name") or "").strip()
    if not name:
        raise ValidationError({"name": "name is required."})
    return {
        "name": name,
        "is_active": bool(merged.get("is_active", True)),
        "schedule": normalize_schedule(merged.get("schedule")),
        "retention": normalize_retention(merged.get("retention")),
        "throttling": normalize_throttling(merged.get("throttling")),
        "error_handling": normalize_error_handling(merged.get("error_handling")),
    }


def create_backup_policy(*, organization_id: int, data: dict[str, Any]) -> BackupPolicy:
    payload = _policy_payload(data)
    try:
        with transaction.atomic():
            return BackupPolicy.objects.create(organization_id=organization_id, **payload)
    except IntegrityError as exc:
        raise ValidationError({"name": "A backup policy with this name already exists."}) from exc


def update_backup_policy(*, policy: BackupPolicy, data: dict[str, Any]) -> BackupPolicy:
    payload = _policy_payload(data, current=policy)
    for field, value in payload.items():
        setattr(policy, field, value)
    try:
        with transaction.atomic():
            policy.save()
    except IntegrityError as exc:
        raise ValidationError({"name": "A backup policy with this name already exists."}) from exc
    return policy


def backup_policy_related_count(*, policy: BackupPolicy) -> int:
    return BackupConfig.objects.filter(
        organization_id=policy.organization_id,
        backup_policy_id=policy.id,
    ).count()


def ensure_backup_policy_not_referenced(*, policy: BackupPolicy) -> None:
    if backup_policy_related_count(policy=policy) > 0:
        raise ResourceInUseError("Backup policy is referenced by backup configs.")


def delete_backup_policy(*, policy: BackupPolicy) -> dict[str, Any]:
    policy_id = int(policy.id)
    ensure_backup_policy_not_referenced(policy=policy)
    policy.delete()
    return {"deleted": True, "id": policy_id}


def bulk_set_backup_policy_state(
    *,
    organization_id: int,
    ids: list[int],
    is_active: bool,
) -> dict[str, Any]:
    if not ids:
        raise ValidationError({"ids": "ids must not be empty."})
    existing = list(
        BackupPolicy.objects.filter(organization_id=organization_id, id__in=ids)
    )
    by_id = {int(policy.id): policy for policy in existing}
    updated: list[int] = []
    failed = [
        BulkFailure(id=policy_id, reason="not_found")
        for policy_id in ids
        if policy_id not in by_id
    ]
    with transaction.atomic():
        for policy in existing:
            if policy.is_active != is_active:
                policy.is_active = is_active
                policy.save(update_fields=["is_active", "updated_at"])
            updated.append(int(policy.id))
    return {"updated": updated, "failed": [failure.__dict__ for failure in failed]}


def bulk_delete_backup_policies(*, organization_id: int, ids: list[int]) -> dict[str, Any]:
    if not ids:
        raise ValidationError({"ids": "ids must not be empty."})
    existing = list(
        BackupPolicy.objects.filter(organization_id=organization_id, id__in=ids)
    )
    by_id = {int(policy.id): policy for policy in existing}
    deleted: list[int] = []
    failed = [
        BulkFailure(id=policy_id, reason="not_found")
        for policy_id in ids
        if policy_id not in by_id
    ]
    for policy in existing:
        try:
            result = delete_backup_policy(policy=policy)
            deleted.append(int(result["id"]))
        except ResourceInUseError as exc:
            failed.append(BulkFailure(id=int(policy.id), reason=str(exc)))
    return {"deleted": deleted, "failed": [failure.__dict__ for failure in failed]}


def _file_filter_payload(
    data: dict[str, Any],
    current: FileFilterRule | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if current is not None:
        merged = {
            "name": current.name,
            "is_active": current.is_active,
            "ignore_patterns": current.ignore_patterns,
            "large_file_limit_enabled": current.large_file_limit_enabled,
            "large_file_bytes_max": current.large_file_bytes_max,
            "ignore_cache_directories": current.ignore_cache_directories,
            "current_filesystem_only": current.current_filesystem_only,
        }
    merged.update(data)
    name = str(merged.get("name") or "").strip()
    if not name:
        raise ValidationError({"name": "name is required."})
    large_file_limit_enabled = bool(merged.get("large_file_limit_enabled", False))
    large_file_bytes_max = _int(merged, "large_file_bytes_max")
    if large_file_limit_enabled and large_file_bytes_max <= 0:
        raise ValidationError(
            {"large_file_bytes_max": "large_file_bytes_max must be greater than 0."}
        )
    if not large_file_limit_enabled:
        large_file_bytes_max = 0
    return {
        "name": name,
        "is_active": bool(merged.get("is_active", True)),
        "ignore_patterns": normalize_ignore_patterns(merged.get("ignore_patterns")),
        "large_file_limit_enabled": large_file_limit_enabled,
        "large_file_bytes_max": large_file_bytes_max,
        "ignore_cache_directories": bool(merged.get("ignore_cache_directories", True)),
        "current_filesystem_only": bool(merged.get("current_filesystem_only", False)),
    }


def create_file_filter_rule(*, organization_id: int, data: dict[str, Any]) -> FileFilterRule:
    payload = _file_filter_payload(data)
    try:
        with transaction.atomic():
            return FileFilterRule.objects.create(organization_id=organization_id, **payload)
    except IntegrityError as exc:
        raise ValidationError(
            {"name": "A file filter rule with this name already exists."}
        ) from exc


def update_file_filter_rule(
    *,
    rule: FileFilterRule,
    data: dict[str, Any],
) -> FileFilterRule:
    payload = _file_filter_payload(data, current=rule)
    for field, value in payload.items():
        setattr(rule, field, value)
    try:
        with transaction.atomic():
            rule.save()
    except IntegrityError as exc:
        raise ValidationError(
            {"name": "A file filter rule with this name already exists."}
        ) from exc
    return rule


def file_filter_related_count(*, rule: FileFilterRule) -> int:
    return BackupConfig.objects.filter(
        organization_id=rule.organization_id,
        file_filter_rule_id=rule.id,
    ).count()


def ensure_file_filter_not_referenced(*, rule: FileFilterRule) -> None:
    if file_filter_related_count(rule=rule) > 0:
        raise ResourceInUseError("File filter rule is referenced by backup configs.")


def delete_file_filter_rule(*, rule: FileFilterRule) -> dict[str, Any]:
    rule_id = int(rule.id)
    ensure_file_filter_not_referenced(rule=rule)
    rule.delete()
    return {"deleted": True, "id": rule_id}


def bulk_set_file_filter_state(
    *,
    organization_id: int,
    ids: list[int],
    is_active: bool,
) -> dict[str, Any]:
    if not ids:
        raise ValidationError({"ids": "ids must not be empty."})
    existing = list(
        FileFilterRule.objects.filter(organization_id=organization_id, id__in=ids)
    )
    by_id = {int(rule.id): rule for rule in existing}
    updated: list[int] = []
    failed = [
        BulkFailure(id=rule_id, reason="not_found")
        for rule_id in ids
        if rule_id not in by_id
    ]
    with transaction.atomic():
        for rule in existing:
            if rule.is_active != is_active:
                rule.is_active = is_active
                rule.save(update_fields=["is_active", "updated_at"])
            updated.append(int(rule.id))
    return {"updated": updated, "failed": [failure.__dict__ for failure in failed]}


def bulk_delete_file_filters(*, organization_id: int, ids: list[int]) -> dict[str, Any]:
    if not ids:
        raise ValidationError({"ids": "ids must not be empty."})
    existing = list(
        FileFilterRule.objects.filter(organization_id=organization_id, id__in=ids)
    )
    by_id = {int(rule.id): rule for rule in existing}
    deleted: list[int] = []
    failed = [
        BulkFailure(id=rule_id, reason="not_found")
        for rule_id in ids
        if rule_id not in by_id
    ]
    for rule in existing:
        try:
            result = delete_file_filter_rule(rule=rule)
            deleted.append(int(result["id"]))
        except ResourceInUseError as exc:
            failed.append(BulkFailure(id=int(rule.id), reason=str(exc)))
    return {"deleted": deleted, "failed": [failure.__dict__ for failure in failed]}
