from __future__ import annotations

from typing import Any

from apps.protection.models import BackupPolicy


def backup_policy_agent_payload(
    policy: BackupPolicy | None,
    *,
    bound_policy_id: int | None = None,
) -> dict[str, Any]:
    policy_id = bound_policy_id if bound_policy_id is not None else getattr(policy, "id", None)
    active = bool(policy is not None and policy.is_active)
    if not active:
        return {
            "policy_id": int(policy_id) if policy_id else None,
            "active": False,
            "advanced_settings": {
                "enabled": False,
                "skip_unreadable_directories": False,
                "skip_unreadable_files": False,
                "skip_unsupported_filesystem_entries": False,
            },
        }
    error = policy.error_handling if isinstance(policy.error_handling, dict) else {}
    enabled = bool(error.get("enabled", False))
    return {
        "policy_id": int(policy.id),
        "active": True,
        "advanced_settings": {
            "enabled": enabled,
            "skip_unreadable_directories": enabled
            and bool(error.get("ignore_directory_read_errors", True)),
            "skip_unreadable_files": enabled
            and bool(error.get("ignore_file_read_errors", False)),
            "skip_unsupported_filesystem_entries": enabled
            and bool(error.get("ignore_unknown_entries", True)),
        },
    }
