"""Per-user Copilot usage aggregation and durable HFL usage records."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import time
from typing import Any
import uuid

from django.db.models import Count, F, OrderBy, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import NotFound

from apps.lens_bridge.models import LensSessionLink, LensSlUserLink, LensUsageLedger
from apps.lens_bridge.services import sl_client
from apps.protection.models import BackupConfig, BackupSourceSnapshot
from apps.protection.services.source_identity import resolve_source_display_name


MAX_BACKFILL_RUNS = 500
BACKFILL_TTL_SECONDS = 300
_BACKFILL_REFRESHED_AT: dict[tuple[int, str, str], float] = {}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if hasattr(value, "tzinfo"):
        return value
    parsed = parse_datetime(str(value))
    if parsed is not None and timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _sl_user_link(user) -> LensSlUserLink | None:
    return LensSlUserLink.objects.filter(
        hfl_user=user,
        provision_status=LensSlUserLink.ProvisionStatus.READY,
        sl_user_id__gt=0,
    ).first()


def _session_context(link: LensSessionLink) -> dict[str, Any]:
    backup_source_name = ""
    if link.backup_config_id:
        config = BackupConfig.objects.filter(
            id=link.backup_config_id,
            organization_id=link.organization_id,
        ).first()
        if config is not None:
            backup_source_name = resolve_source_display_name(
                organization_id=link.organization_id,
                source_type=config.source_type,
                source_ref_id=config.source_ref_id,
                fallback=config.name,
            )
    snapshot_created_at = None
    if link.backup_source_snapshot_id:
        snapshot = BackupSourceSnapshot.objects.filter(
            id=link.backup_source_snapshot_id,
            organization_id=link.organization_id,
        ).first()
        if snapshot is not None:
            snapshot_created_at = (
                snapshot.finished_at or snapshot.started_at or snapshot.created_at
            )
    gateway_name = ""
    if link.gateway_selection_mode == LensSessionLink.GatewaySelectionMode.MANUAL:
        gateway_link = link.gateway_link
        if gateway_link is not None and gateway_link.gateway_id:
            gateway_name = gateway_link.gateway.name
    return {
        "session_link": link,
        "sl_session_uuid": link.sl_session_uuid,
        "chat_title": link.title,
        "backup_config_id": link.backup_config_id,
        "backup_source_name": backup_source_name,
        "backup_source_snapshot_id": link.backup_source_snapshot_id,
        "snapshot_created_at": snapshot_created_at,
        "source_scopes_json": list(link.source_scopes_json or []),
        "gateway_selection_mode": link.gateway_selection_mode,
        "gateway_name": gateway_name,
    }


def register_usage_run(
    link: LensSessionLink,
    *,
    run_uuid: uuid.UUID,
    question: str,
    status: str,
) -> LensUsageLedger | None:
    sl_user = _sl_user_link(link.hfl_user)
    if sl_user is None:
        return None
    context = _session_context(link)
    row, _ = LensUsageLedger.objects.update_or_create(
        sl_run_uuid=run_uuid,
        defaults={
            "organization": link.organization,
            "hfl_user": link.hfl_user,
            "sl_user_id": sl_user.sl_user_id,
            "question": question.strip(),
            "run_status": status or "queued",
            "occurred_at": timezone.now(),
            **context,
        },
    )
    return row


def _run_call_details(
    run: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": None,
    }
    total_cost = Decimal("0")
    has_cost = False

    def add_call(payload: dict[str, Any]) -> None:
        nonlocal total_cost, has_cost
        prompt = int(payload.get("prompt_tokens") or 0)
        completion = int(payload.get("completion_tokens") or 0)
        cached = int(payload.get("cached_tokens") or 0)
        reasoning = int(payload.get("reasoning_tokens") or 0)
        total = int(payload.get("total_tokens") or prompt + completion)
        cost = _decimal(payload.get("cost"))
        if cost is not None:
            total_cost += cost
            has_cost = True
        calls.append({
            "call": len(calls) + 1,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "cached_tokens": cached,
            "reasoning_tokens": reasoning,
            "total_tokens": total,
            "estimated_cost": float(cost) if cost is not None else None,
        })
        totals["prompt_tokens"] += prompt
        totals["completion_tokens"] += completion
        totals["cached_tokens"] += cached
        totals["reasoning_tokens"] += reasoning
        totals["total_tokens"] += total

    for step in run.get("steps") or []:
        detail = step.get("detail") if isinstance(step.get("detail"), dict) else step
        for event in detail.get("events") or []:
            if event.get("agent_event") == "llm.response":
                add_call(event)
        usage = detail.get("usage")
        if isinstance(usage, dict) and usage:
            add_call(usage)
    totals["estimated_cost"] = total_cost if has_cost else None
    return calls, totals


def capture_run_usage(link: LensSessionLink, run: dict[str, Any]) -> LensUsageLedger | None:
    raw_uuid = run.get("uuid") or link.active_run_uuid
    if not raw_uuid:
        return None
    run_uuid = uuid.UUID(str(raw_uuid))
    row = LensUsageLedger.objects.filter(sl_run_uuid=run_uuid).first()
    if row is None:
        row = register_usage_run(
            link,
            run_uuid=run_uuid,
            question="",
            status=str(run.get("status") or ""),
        )
    if row is None:
        return None
    calls, totals = _run_call_details(run)
    row.run_status = str(run.get("status") or row.run_status or "")
    row.prompt_tokens = totals["prompt_tokens"]
    row.completion_tokens = totals["completion_tokens"]
    row.cached_tokens = totals["cached_tokens"]
    row.reasoning_tokens = totals["reasoning_tokens"]
    row.total_tokens = totals["total_tokens"]
    row.model_calls = len(calls)
    row.estimated_cost = totals["estimated_cost"]
    row.call_details_json = calls
    row.run_error = str(run.get("error") or "")
    row.started_at = _datetime(run.get("started_at"))
    row.finished_at = _datetime(run.get("finished_at"))
    row.occurred_at = row.started_at or row.occurred_at or timezone.now()
    row.save(update_fields=[
        "run_status",
        "prompt_tokens",
        "completion_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "total_tokens",
        "model_calls",
        "estimated_cost",
        "call_details_json",
        "run_error",
        "started_at",
        "finished_at",
        "occurred_at",
        "updated_at",
    ])
    return row


def _session_by_assistant_name(org, user) -> dict[str, LensSessionLink]:
    rows = LensSessionLink.objects.filter(
        organization=org,
        hfl_user=user,
    ).select_related("knowledge_source", "gateway_link__gateway")
    return {
        row.knowledge_source.name: row
        for row in rows
        if row.knowledge_source is not None and row.knowledge_source.name
    }


def backfill_usage_ledgers(org, user, *, start_date: str, end_date: str) -> None:
    sl_user = _sl_user_link(user)
    if sl_user is None:
        return
    cache_key = (user.pk, start_date, end_date)
    refreshed_at = _BACKFILL_REFRESHED_AT.get(cache_key)
    if refreshed_at is not None and time.monotonic() - refreshed_at < BACKFILL_TTL_SECONDS:
        return
    session_map = _session_by_assistant_name(org, user)
    page = 1
    imported = 0
    while imported < MAX_BACKFILL_RUNS:
        payload = sl_client.request_json(
            "GET",
            "/api/lens/admin/runs/",
            params={
                "username": sl_user.sl_username,
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "page_size": 100,
            },
        )
        results = payload.get("results") if isinstance(payload, dict) else []
        exact_rows = [
            item for item in (results or [])
            if str(item.get("username") or "") == sl_user.sl_username
        ]
        for item in exact_rows:
            raw_uuid = item.get("uuid")
            if not raw_uuid:
                continue
            session = session_map.get(str(item.get("assistant_name") or ""))
            context = _session_context(session) if session is not None else {
                "session_link": None,
                "sl_session_uuid": None,
                "chat_title": "Deleted Chat",
                "backup_config_id": None,
                "backup_source_name": "",
                "backup_source_snapshot_id": None,
                "snapshot_created_at": None,
                "source_scopes_json": [],
                "gateway_selection_mode": "auto",
                "gateway_name": "",
            }
            defaults = {
                "organization": org,
                "hfl_user": user,
                "sl_user_id": sl_user.sl_user_id,
                "question": str(item.get("question") or ""),
                "run_status": str(item.get("status") or ""),
                "prompt_tokens": int(item.get("prompt_tokens") or 0),
                "completion_tokens": int(item.get("completion_tokens") or 0),
                "total_tokens": int(item.get("total_tokens") or 0),
                "model_calls": int(item.get("llm_calls") or 0),
                "estimated_cost": _decimal(item.get("total_cost")),
                "started_at": _datetime(item.get("started_at")),
                "finished_at": _datetime(item.get("finished_at")),
                "occurred_at": (
                    _datetime(item.get("started_at") or item.get("created_at"))
                    or timezone.now()
                ),
                **context,
            }
            LensUsageLedger.objects.update_or_create(
                sl_run_uuid=uuid.UUID(str(raw_uuid)),
                defaults=defaults,
            )
        imported += len(results or [])
        total = int(payload.get("total") or 0) if isinstance(payload, dict) else 0
        if not results or page * 100 >= total:
            break
        page += 1
    if len(_BACKFILL_REFRESHED_AT) > 1000:
        _BACKFILL_REFRESHED_AT.clear()
    _BACKFILL_REFRESHED_AT[cache_key] = time.monotonic()


def _date_range(params) -> tuple[str, str]:
    today = timezone.localdate()
    default_start = today
    raw_start = str(params.get("start_date") or "")
    raw_end = str(params.get("end_date") or "")
    start = parse_date(raw_start) or default_start
    end = parse_date(raw_end) or today
    if start > end:
        start, end = end, start
    return start.isoformat(), end.isoformat()


def _scope_summary(scopes: list[dict[str, Any]]) -> str:
    if not scopes:
        return "No Content"
    types = [str(item.get("path_type") or "unknown") for item in scopes]
    if all(value == "file" for value in types):
        label = "File"
    elif all(value == "dir" for value in types):
        label = "Folder"
    else:
        label = "Item"
    return f"{len(scopes)} {label}{'' if len(scopes) == 1 else 's'}"


def _ledger_item(row: LensUsageLedger) -> dict[str, Any]:
    return {
        "run_uuid": str(row.sl_run_uuid),
        "time": row.occurred_at,
        "chat_id": row.session_link_id,
        "chat_title": row.chat_title or "Deleted Chat",
        "chat_available": bool(
            row.session_link_id
            and row.session_link
            and row.session_link.lifecycle_status != LensSessionLink.LifecycleStatus.DELETED
        ),
        "backup_source_name": row.backup_source_name or "Backup Source",
        "scope_summary": _scope_summary(list(row.source_scopes_json or [])),
        "question": row.question,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "cached_tokens": row.cached_tokens,
        "reasoning_tokens": row.reasoning_tokens,
        "total_tokens": row.total_tokens,
        "model_calls": row.model_calls,
        "estimated_cost": float(row.estimated_cost) if row.estimated_cost is not None else None,
        "cost_currency": row.cost_currency,
        "status": row.run_status,
    }


def _trend_item(bucket: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "bucket": bucket,
        "total_calls": row.get("total_calls") or 0,
        "total_prompt_tokens": row.get("total_prompt_tokens") or 0,
        "total_completion_tokens": row.get("total_completion_tokens") or 0,
        "total_cached_tokens": row.get("total_cached_tokens") or 0,
        "total_reasoning_tokens": row.get("total_reasoning_tokens") or 0,
        "total_tokens": row.get("total_tokens") or 0,
        "total_cost": (
            float(row["total_cost"])
            if row.get("total_cost") is not None
            else 0
        ),
    }


def usage_overview(org, user, params) -> dict[str, Any]:
    start_date, end_date = _date_range(params)
    sl_user = _sl_user_link(user)
    if sl_user is None:
        return {
            "period": {"start_date": start_date, "end_date": end_date},
            "summary": {
                "estimated_cost": 0,
                "cost_currency": "USD",
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
                "model_calls": 0,
                "q_and_a_requests": 0,
                "average_cost_per_q_and_a": 0,
            },
            "trend": [],
            "by_backup_source": [],
            "backup_sources": [],
            "results": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }

    backfill_usage_ledgers(org, user, start_date=start_date, end_date=end_date)

    start = parse_date(start_date)
    end = parse_date(end_date)
    queryset = LensUsageLedger.objects.filter(
        organization=org,
        hfl_user=user,
        occurred_at__date__gte=start,
        occurred_at__date__lte=end,
    ).select_related("session_link")
    query = str(params.get("q") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(question__icontains=query)
            | Q(chat_title__icontains=query)
            | Q(backup_source_name__icontains=query)
        )
    backup_source = str(params.get("backup_source") or "").strip()
    if backup_source:
        queryset = queryset.filter(backup_source_name=backup_source)
    run_status = str(params.get("status") or "").strip()
    if run_status:
        queryset = queryset.filter(run_status=run_status)

    try:
        page = max(1, int(params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(params.get("page_size") or 20)))
    except (TypeError, ValueError):
        page_size = 20
    total = queryset.count()
    offset = (page - 1) * page_size
    results = [_ledger_item(row) for row in queryset[offset:offset + page_size]]

    period_rows = LensUsageLedger.objects.filter(
        organization=org,
        hfl_user=user,
        occurred_at__date__gte=start,
        occurred_at__date__lte=end,
    )
    q_and_a_requests = period_rows.count()
    period_totals = period_rows.aggregate(
        prompt_tokens=Sum("prompt_tokens"),
        completion_tokens=Sum("completion_tokens"),
        cached_tokens=Sum("cached_tokens"),
        reasoning_tokens=Sum("reasoning_tokens"),
        total_tokens=Sum("total_tokens"),
        model_calls=Sum("model_calls"),
        estimated_cost=Sum("estimated_cost"),
    )
    same_day = start == end
    bucket_expression = (
        TruncHour("occurred_at") if same_day else TruncDate("occurred_at")
    )
    trend_rows = period_rows.annotate(bucket=bucket_expression).values(
        "bucket"
    ).annotate(
        total_calls=Sum("model_calls"),
        total_prompt_tokens=Sum("prompt_tokens"),
        total_completion_tokens=Sum("completion_tokens"),
        total_cached_tokens=Sum("cached_tokens"),
        total_reasoning_tokens=Sum("reasoning_tokens"),
        total_tokens=Sum("total_tokens"),
        total_cost=Sum("estimated_cost"),
    ).order_by("bucket")
    trend_index = {
        row["bucket"].isoformat(): row
        for row in trend_rows
        if row["bucket"] is not None
    }
    trend = []
    if same_day:
        start_of_day = timezone.make_aware(
            datetime.combine(start, datetime.min.time()),
            timezone.get_current_timezone(),
        )
        final_hour = 23
        if end == timezone.localdate():
            final_hour = timezone.localtime().hour
        for hour in range(final_hour + 1):
            cursor = start_of_day + timedelta(hours=hour)
            bucket = cursor.isoformat()
            row = trend_index.get(bucket) or {}
            trend.append(_trend_item(bucket, row))
    else:
        cursor = start
        while cursor <= end:
            bucket = cursor.isoformat()
            row = trend_index.get(bucket) or {}
            trend.append(_trend_item(bucket, row))
            cursor += timedelta(days=1)
    by_source = period_rows.values("backup_source_name").annotate(
        q_and_a_requests=Count("id"),
        model_calls=Sum("model_calls"),
        total_tokens=Sum("total_tokens"),
        estimated_cost=Sum("estimated_cost"),
    ).order_by(
        OrderBy(F("estimated_cost"), descending=True, nulls_last=True),
        "-total_tokens",
        "backup_source_name",
    )

    total_cost = float(period_totals["estimated_cost"] or 0)
    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "estimated_cost": total_cost,
            "cost_currency": "USD",
            "total_tokens": int(period_totals["total_tokens"] or 0),
            "prompt_tokens": int(period_totals["prompt_tokens"] or 0),
            "completion_tokens": int(period_totals["completion_tokens"] or 0),
            "cached_tokens": int(period_totals["cached_tokens"] or 0),
            "reasoning_tokens": int(period_totals["reasoning_tokens"] or 0),
            "model_calls": int(period_totals["model_calls"] or 0),
            "q_and_a_requests": q_and_a_requests,
            "average_cost_per_q_and_a": (
                total_cost / q_and_a_requests if q_and_a_requests else 0
            ),
        },
        "trend": trend,
        "by_backup_source": [
            {
                "backup_source_name": row["backup_source_name"] or "Backup Source",
                "q_and_a_requests": row["q_and_a_requests"],
                "model_calls": row["model_calls"] or 0,
                "total_tokens": row["total_tokens"] or 0,
                "estimated_cost": (
                    float(row["estimated_cost"])
                    if row["estimated_cost"] is not None
                    else None
                ),
            }
            for row in by_source
        ],
        "backup_sources": list(
            period_rows.exclude(backup_source_name="")
            .order_by("backup_source_name")
            .values_list("backup_source_name", flat=True)
            .distinct()
        ),
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def usage_detail(org, user, run_uuid: uuid.UUID) -> dict[str, Any]:
    row = LensUsageLedger.objects.select_related("session_link").filter(
        organization=org,
        hfl_user=user,
        sl_run_uuid=run_uuid,
    ).first()
    if row is None:
        raise NotFound()
    if not row.call_details_json:
        sl_user = _sl_user_link(user)
        if sl_user is not None:
            try:
                payload = sl_client.request_json("GET", f"/api/lens/admin/runs/{run_uuid}/")
                if str(payload.get("username") or "") == sl_user.sl_username:
                    calls, totals = _run_call_details(payload)
                    row.question = str(payload.get("question") or row.question)
                    row.call_details_json = calls
                    row.prompt_tokens = totals["prompt_tokens"] or row.prompt_tokens
                    row.completion_tokens = totals["completion_tokens"] or row.completion_tokens
                    row.cached_tokens = totals["cached_tokens"] or row.cached_tokens
                    row.reasoning_tokens = totals["reasoning_tokens"] or row.reasoning_tokens
                    row.total_tokens = totals["total_tokens"] or row.total_tokens
                    row.model_calls = len(calls) or row.model_calls
                    if totals["estimated_cost"] is not None:
                        row.estimated_cost = totals["estimated_cost"]
                    row.save(update_fields=[
                        "question",
                        "call_details_json",
                        "prompt_tokens",
                        "completion_tokens",
                        "cached_tokens",
                        "reasoning_tokens",
                        "total_tokens",
                        "model_calls",
                        "estimated_cost",
                        "updated_at",
                    ])
            except sl_client.LensBridgeError:
                pass
    payload = _ledger_item(row)
    payload.update({
        "snapshot_created_at": row.snapshot_created_at,
        "source_scopes": list(row.source_scopes_json or []),
        "gateway_mode": row.gateway_selection_mode,
        "gateway_name": row.gateway_name,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "error": row.run_error,
        "call_details": list(row.call_details_json or []),
    })
    return payload
