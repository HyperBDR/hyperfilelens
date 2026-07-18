from __future__ import annotations

from typing import Any

from apps.protection.models import FileFilterRule


def file_filter_agent_payload(
    rule: FileFilterRule | None,
    *,
    bound_rule_id: int | None = None,
) -> dict[str, Any]:
    rule_id = bound_rule_id if bound_rule_id is not None else getattr(rule, "id", None)
    active = bool(rule is not None and rule.is_active)
    if not active:
        return {
            "rule_id": int(rule_id) if rule_id else None,
            "active": False,
            "configured": False,
            "ignore_patterns": [],
            "large_file_limit_enabled": False,
            "large_file_bytes_max": 0,
            "ignore_cache_directories": False,
            "current_filesystem_only": False,
        }
    patterns = [line.strip() for line in rule.ignore_patterns.splitlines() if line.strip()]
    return {
        "rule_id": int(rule.id) if rule.id else None,
        "active": True,
        "configured": True,
        "ignore_patterns": patterns,
        "large_file_limit_enabled": bool(rule.large_file_limit_enabled),
        "large_file_bytes_max": (
            int(rule.large_file_bytes_max or 0)
            if rule.large_file_limit_enabled
            else 0
        ),
        "ignore_cache_directories": bool(rule.ignore_cache_directories),
        "current_filesystem_only": bool(rule.current_filesystem_only),
    }
