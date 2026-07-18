from __future__ import annotations

from rest_framework import serializers

from apps.node import agent_paths
from apps.source.constants import ResourceType


def _validate_agent_mount_path(path: str) -> None:
    try:
        agent_paths.require_agent_mount_path(path)
    except ValueError as exc:
        raise serializers.ValidationError({"config": str(exc)}) from exc


def validate_resource_payload(*, resource_type: str, config: dict, credentials: dict) -> None:
    config = config or {}
    credentials = credentials or {}

    if resource_type == ResourceType.NFS:
        if not config.get("server"):
            raise serializers.ValidationError({"config": 'NFS requires "server"'})
        if not (config.get("export_path") or config.get("path")):
            raise serializers.ValidationError({"config": 'NFS requires "export_path"'})
    elif resource_type == ResourceType.CIFS:
        if not config.get("server"):
            raise serializers.ValidationError({"config": 'CIFS requires "server"'})
        if not config.get("share"):
            raise serializers.ValidationError({"config": 'CIFS requires "share"'})
        if not credentials.get("username") or not credentials.get("password"):
            raise serializers.ValidationError(
                {"credentials": 'CIFS requires "username" and "password"'}
            )
    elif resource_type == ResourceType.NAS:
        if not config.get("server"):
            raise serializers.ValidationError({"config": 'NAS requires "server"'})
        mount_path = str(config.get("path") or "").strip()
        if mount_path:
            _validate_agent_mount_path(mount_path)
        protocol = str(config.get("protocol") or "").strip().lower()
        has_share = bool(str(config.get("share") or "").strip())
        if protocol == "smb" or has_share:
            if not credentials.get("username") or not credentials.get("password"):
                raise serializers.ValidationError(
                    {"credentials": 'NAS SMB/CIFS requires "username" and "password"'}
                )
        elif protocol == "nfs" or config.get("export_path"):
            if not (config.get("export_path") or config.get("path")):
                raise serializers.ValidationError({"config": 'NAS NFS requires "export_path"'})
    elif resource_type == ResourceType.S3:
        if not config.get("endpoint"):
            raise serializers.ValidationError({"config": 'S3 requires "endpoint"'})
        if not config.get("bucket"):
            raise serializers.ValidationError({"config": 'S3 requires "bucket"'})
        if not credentials.get("access_key") or not credentials.get("secret_key"):
            raise serializers.ValidationError(
                {"credentials": 'S3 requires "access_key" and "secret_key"'}
            )
    elif resource_type == ResourceType.LOCAL:
        if not (config.get("root_path") or config.get("path")):
            raise serializers.ValidationError({"config": 'LOCAL requires "root_path" or "path"'})
