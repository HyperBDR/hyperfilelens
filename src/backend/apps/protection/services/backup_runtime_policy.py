from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from apps.protection.models import BackupConfig, BackupPolicy, FileFilterRule
from apps.protection.services.backup_policy_runtime import backup_policy_agent_payload
from apps.protection.services.file_filter_runtime import file_filter_agent_payload

POLICY_SNAPSHOT_VERSION = 1

SYSTEM_NEVER_COMPRESS_EXTENSIONS = (
    ".7z",
    ".aac",
    ".apk",
    ".avi",
    ".bz2",
    ".flac",
    ".gif",
    ".gz",
    ".heic",
    ".heif",
    ".iso",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".pdf",
    ".png",
    ".rar",
    ".tgz",
    ".webp",
    ".xz",
    ".zip",
    ".zst",
)

_COMPRESSION_PROFILES: dict[str, dict[str, Any]] = {
    BackupConfig.CompressionLevel.NONE: {
        "compressor": "none",
        "minimum_file_size_bytes": 0,
        "maximum_file_size_bytes": 0,
        "only_extensions": [],
        "never_extensions": [],
    },
    BackupConfig.CompressionLevel.BALANCED: {
        "compressor": "zstd",
        "minimum_file_size_bytes": 4096,
        "maximum_file_size_bytes": 0,
        "only_extensions": [],
        "never_extensions": list(SYSTEM_NEVER_COMPRESS_EXTENSIONS),
    },
    BackupConfig.CompressionLevel.HIGH: {
        "compressor": "zstd-better-compression",
        "minimum_file_size_bytes": 4096,
        "maximum_file_size_bytes": 0,
        "only_extensions": [],
        "never_extensions": list(SYSTEM_NEVER_COMPRESS_EXTENSIONS),
    },
}


def compression_agent_payload(level: str) -> dict[str, Any]:
    normalized = str(level or "").strip().lower()
    profile = _COMPRESSION_PROFILES.get(normalized)
    if profile is None:
        raise ValidationError(
            {"compression_level": "Must be one of: balanced, high, none."}
        )
    return {
        "level": normalized,
        "compressor": profile["compressor"],
        "minimum_file_size_bytes": profile["minimum_file_size_bytes"],
        "maximum_file_size_bytes": profile["maximum_file_size_bytes"],
        "only_extensions": list(profile["only_extensions"]),
        "never_extensions": list(profile["never_extensions"]),
    }


def build_backup_runtime_policy(*, config: BackupConfig) -> dict[str, Any]:
    file_filter = None
    if config.file_filter_rule_id:
        file_filter = FileFilterRule.objects.filter(
            organization_id=config.organization_id,
            id=config.file_filter_rule_id,
        ).first()

    backup_policy = None
    if config.backup_policy_id:
        backup_policy = BackupPolicy.objects.filter(
            organization_id=config.organization_id,
            id=config.backup_policy_id,
        ).first()

    return {
        "version": POLICY_SNAPSHOT_VERSION,
        "file_filter": file_filter_agent_payload(
            file_filter,
            bound_rule_id=config.file_filter_rule_id,
        ),
        "backup_policy": backup_policy_agent_payload(
            backup_policy,
            bound_policy_id=config.backup_policy_id,
        ),
        "compression": compression_agent_payload(config.compression_level),
    }


def backup_runtime_policy_payload(policy_snapshot: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(policy_snapshot, dict):
        raise ValidationError({"policy_snapshot": "Runtime policy snapshot is missing."})
    if int(policy_snapshot.get("version") or 0) != POLICY_SNAPSHOT_VERSION:
        raise ValidationError({"policy_snapshot": "Unsupported runtime policy version."})

    result: dict[str, dict[str, Any]] = {}
    for key in ("file_filter", "backup_policy", "compression"):
        value = policy_snapshot.get(key)
        if not isinstance(value, dict):
            raise ValidationError({"policy_snapshot": f"{key} is required."})
        result[key] = dict(value)
    return result
