"""Platform Ops system infrastructure APIs."""

from __future__ import annotations

import os
import re
from collections import Counter, deque
from datetime import timedelta
from pathlib import Path

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.platform import PlatformAuditLogSerializer
from apps.platform_ops.api.views._utils import paginated, safe_int
from apps.platform_ops.selectors.internal.security import list_platform_audit_logs
from apps.platform_ops.selectors.internal.system import (
    migration_status,
    system_health_payload,
    table_row_counts,
)


class PlatformOpsSystemHealthView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        return Response(system_health_payload())


class PlatformOpsSystemDatabaseView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        return Response(
            {
                "table_counts": table_row_counts(),
                "migrations": migration_status(),
            }
        )


class PlatformOpsSystemAuditView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20, max_value=200)
        qs = list_platform_audit_logs(
            search=request.query_params.get("search", ""),
            action=request.query_params.get("action", ""),
            result=request.query_params.get("result", ""),
            org_key=request.query_params.get("org", ""),
        )
        total = qs.count()
        all_logs = list_platform_audit_logs()
        stats = {
            "total": all_logs.count(),
            "successful": all_logs.filter(result="success").count(),
            "failed": all_logs.filter(result="failed").count(),
            "last_24_hours": all_logs.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
        }
        offset = (page - 1) * page_size
        rows = qs[offset : offset + page_size]
        return Response(
            paginated(
                PlatformAuditLogSerializer(rows, many=True).data,
                total=total,
                page=page,
                page_size=page_size,
                extra={"stats": stats},
            )
        )


_LOG_LINE = re.compile(
    r"^\[?(?P<time>\d{4}-\d{2}-\d{2}[T ][^ \]]+)\]?\s+"
    r"(?:\[(?P<level_bracket>[A-Za-z]+)\]|(?P<level>[A-Za-z]+))\s+"
    r"(?P<message>.*)$"
)
_LOG_LEVEL = re.compile(r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b", re.I)
_SENSITIVE_VALUE = re.compile(
    r"(?i)(password|secret|token|api[_-]?key)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_SENSITIVE_HEADER = re.compile(
    r"(?i)(authorization|cookie)(\s*[:=]\s*)(.+)$"
)


def _redact_log_message(value: str) -> str:
    redacted = _SENSITIVE_HEADER.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        value,
    )
    return _SENSITIVE_VALUE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        redacted,
    )


def _read_log_rows() -> list[dict[str, str | int]]:
    root = Path(os.getenv("HFL_LOG_DIR", "/var/log/hyperfilelens"))
    if not root.is_dir():
        return []
    rows: list[dict[str, str | int]] = []
    for path in sorted(root.glob("*.log")):
        service = path.stem
        try:
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                lines = deque(stream, maxlen=2000)
        except OSError:
            continue
        for line_number, raw in enumerate(lines, start=1):
            line = raw.rstrip("\r\n")
            if not line:
                continue
            match = _LOG_LINE.match(line)
            level_match = _LOG_LEVEL.search(line)
            level = (
                (match.group("level_bracket") or match.group("level"))
                if match
                else level_match.group(1) if level_match else "INFO"
            ).upper()
            if level == "WARN":
                level = "WARNING"
            rows.append(
                {
                    "id": f"{service}:{line_number}",
                    "timestamp": match.group("time") if match else "",
                    "level": level,
                    "service": service,
                    "message": _redact_log_message(
                        match.group("message") if match else line
                    ),
                }
            )
    rows.sort(
        key=lambda row: (str(row["timestamp"]), str(row["id"])),
        reverse=True,
    )
    return rows


class PlatformOpsSystemLogsView(APIView):
    """Read a bounded, redacted view of deployment log files."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        rows = _read_log_rows()
        levels = Counter(str(row["level"]) for row in rows)
        services = Counter(str(row["service"]) for row in rows)
        stats = {
            "total": len(rows),
            "errors": levels["ERROR"] + levels["CRITICAL"] + levels["FATAL"],
            "warnings": levels["WARNING"],
            "services": len(services),
        }
        search = str(request.query_params.get("search") or "").strip().lower()
        level = str(request.query_params.get("level") or "").strip().upper()
        service = str(request.query_params.get("service") or "").strip()
        if search:
            rows = [
                row
                for row in rows
                if search in str(row["message"]).lower()
                or search in str(row["service"]).lower()
            ]
        if level:
            rows = [row for row in rows if row["level"] == level]
        if service:
            rows = [row for row in rows if row["service"] == service]
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 50, max_value=200)
        total = len(rows)
        offset = (page - 1) * page_size
        return Response(
            paginated(
                rows[offset : offset + page_size],
                total=total,
                page=page,
                page_size=page_size,
                extra={
                    "stats": stats,
                    "service_options": sorted(services),
                },
            )
        )
