"""Platform-wide AI usage aggregates for the Admin Console."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.lens_bridge.models import LensUsageLedger


SUCCESS_STATUSES = ("done", "success", "completed")
FAILED_STATUSES = ("failed", "error")


def _safe_int(value, default: int, *, max_value: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(max_value, parsed))


def _date_range(params) -> tuple[Any, Any]:
    today = timezone.localdate()
    start = parse_date(str(params.get("start_date") or "")) or today
    end = parse_date(str(params.get("end_date") or "")) or today
    if start > end:
        start, end = end, start
    return start, end


def _filtered_rows(params):
    start, end = _date_range(params)
    period_rows = LensUsageLedger.objects.filter(
        occurred_at__date__gte=start,
        occurred_at__date__lte=end,
    )
    rows = period_rows
    org_key = str(params.get("org") or "").strip()
    if org_key:
        rows = rows.filter(organization__key=org_key)
    status = str(params.get("status") or "").strip()
    if status:
        rows = rows.filter(run_status=status)
    search = str(params.get("search") or "").strip()
    if search:
        rows = rows.filter(
            Q(organization__key__icontains=search)
            | Q(organization__name__icontains=search)
            | Q(hfl_user__email__icontains=search)
            | Q(question__icontains=search)
            | Q(chat_title__icontains=search)
            | Q(backup_source_name__icontains=search)
        )
    return start, end, period_rows, rows


def _summary(rows) -> dict[str, int | float | str]:
    totals = rows.aggregate(
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        cached_tokens=Sum("cached_tokens"),
        reasoning_tokens=Sum("reasoning_tokens"),
        total_tokens=Sum("total_tokens"),
        model_calls=Sum("model_calls"),
        estimated_cost=Sum("estimated_cost"),
    )
    requests = rows.count()
    successful = rows.filter(run_status__in=SUCCESS_STATUSES).count()
    failed = rows.filter(run_status__in=FAILED_STATUSES).count()
    terminal = successful + failed
    return {
        "estimated_cost": float(totals["estimated_cost"] or 0),
        "cost_currency": "USD",
        "total_tokens": int(totals["total_tokens"] or 0),
        "prompt_tokens": int(totals["prompt_tokens"] or 0),
        "completion_tokens": int(totals["completion_tokens"] or 0),
        "cached_tokens": int(totals["cached_tokens"] or 0),
        "reasoning_tokens": int(totals["reasoning_tokens"] or 0),
        "model_calls": int(totals["model_calls"] or 0),
        "requests": requests,
        "successful_runs": successful,
        "failed_runs": failed,
        "success_rate": round((successful / terminal) * 100, 1) if terminal else 0,
        "organizations": rows.values("organization_id").distinct().count(),
        "users": rows.exclude(hfl_user_id=None).values("hfl_user_id").distinct().count(),
    }


def _trend(rows, *, start, end) -> list[dict[str, Any]]:
    same_day = start == end
    bucket_expression = TruncHour("occurred_at") if same_day else TruncDate("occurred_at")
    aggregates = (
        rows.annotate(bucket=bucket_expression)
        .values("bucket")
        .annotate(
            requests=Count("id"),
            successful_runs=Count("id", filter=Q(run_status__in=SUCCESS_STATUSES)),
            failed_runs=Count("id", filter=Q(run_status__in=FAILED_STATUSES)),
            model_calls=Sum("model_calls"),
            total_tokens=Sum("total_tokens"),
            estimated_cost=Sum("estimated_cost"),
        )
        .order_by("bucket")
    )
    index = {
        row["bucket"].isoformat(): row
        for row in aggregates
        if row["bucket"] is not None
    }
    buckets: list[Any] = []
    if same_day:
        cursor = timezone.make_aware(
            datetime.combine(start, datetime.min.time()),
            timezone.get_current_timezone(),
        )
        final_hour = timezone.localtime().hour if end == timezone.localdate() else 23
        buckets = [cursor + timedelta(hours=hour) for hour in range(final_hour + 1)]
    else:
        cursor = start
        while cursor <= end:
            buckets.append(cursor)
            cursor += timedelta(days=1)
    return [
        {
            "bucket": bucket.isoformat(),
            "requests": int((index.get(bucket.isoformat()) or {}).get("requests") or 0),
            "successful_runs": int(
                (index.get(bucket.isoformat()) or {}).get("successful_runs") or 0
            ),
            "failed_runs": int(
                (index.get(bucket.isoformat()) or {}).get("failed_runs") or 0
            ),
            "model_calls": int(
                (index.get(bucket.isoformat()) or {}).get("model_calls") or 0
            ),
            "total_tokens": int(
                (index.get(bucket.isoformat()) or {}).get("total_tokens") or 0
            ),
            "estimated_cost": float(
                (index.get(bucket.isoformat()) or {}).get("estimated_cost") or 0
            ),
        }
        for bucket in buckets
    ]


def _organization_usage(rows) -> list[dict[str, Any]]:
    aggregates = (
        rows.values(
            "organization_id",
            "organization__key",
            "organization__name",
        )
        .annotate(
            users=Count("hfl_user_id", distinct=True),
            requests=Count("id"),
            successful_runs=Count("id", filter=Q(run_status__in=SUCCESS_STATUSES)),
            failed_runs=Count("id", filter=Q(run_status__in=FAILED_STATUSES)),
            model_calls=Sum("model_calls"),
            total_tokens=Sum("total_tokens"),
            estimated_cost=Sum("estimated_cost"),
        )
        .order_by("-estimated_cost", "-total_tokens", "organization__key")
    )
    output = []
    for row in aggregates:
        terminal = int(row["successful_runs"] or 0) + int(row["failed_runs"] or 0)
        output.append(
            {
                "organization_id": row["organization_id"],
                "organization_key": row["organization__key"],
                "organization_name": row["organization__name"],
                "users": int(row["users"] or 0),
                "requests": int(row["requests"] or 0),
                "model_calls": int(row["model_calls"] or 0),
                "total_tokens": int(row["total_tokens"] or 0),
                "estimated_cost": float(row["estimated_cost"] or 0),
                "failed_runs": int(row["failed_runs"] or 0),
                "success_rate": round(
                    (int(row["successful_runs"] or 0) / terminal) * 100,
                    1,
                )
                if terminal
                else 0,
            }
        )
    return output


def platform_ai_usage_payload(params) -> dict[str, Any]:
    start, end, period_rows, rows = _filtered_rows(params)
    page = _safe_int(params.get("page"), 1)
    page_size = _safe_int(params.get("page_size"), 20)
    total = rows.count()
    offset = (page - 1) * page_size
    result_rows = rows.select_related("organization", "hfl_user").order_by(
        "-occurred_at",
        "-id",
    )[offset : offset + page_size]
    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "summary": _summary(rows),
        "trend": _trend(rows, start=start, end=end),
        "by_organization": _organization_usage(rows),
        "organization_options": [
            {"key": row["organization__key"], "name": row["organization__name"]}
            for row in period_rows.values(
                "organization__key",
                "organization__name",
            )
            .order_by("organization__name", "organization__key")
            .distinct()
        ],
        "status_options": list(
            period_rows.exclude(run_status="")
            .order_by("run_status")
            .values_list("run_status", flat=True)
            .distinct()
        ),
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": [
            {
                "run_uuid": str(row.sl_run_uuid),
                "time": row.occurred_at,
                "organization_id": row.organization_id,
                "organization_key": row.organization.key,
                "organization_name": row.organization.name,
                "user_id": row.hfl_user_id,
                "user_email": row.hfl_user.email if row.hfl_user else "",
                "question": row.question,
                "chat_title": row.chat_title,
                "backup_source_name": row.backup_source_name,
                "status": row.run_status,
                "model_calls": row.model_calls,
                "total_tokens": row.total_tokens,
                "estimated_cost": (
                    float(row.estimated_cost)
                    if row.estimated_cost is not None
                    else None
                ),
                "cost_currency": row.cost_currency,
                "error": row.run_error,
            }
            for row in result_rows
        ],
    }
