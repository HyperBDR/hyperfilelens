from __future__ import annotations

from rest_framework import serializers

from apps.protection.models import (
    BackupSourceSnapshot,
    BackupSourceSnapshotDirectory,
)

_SNAPSHOT_SIZE_KEYS = ("size_bytes", "sizeBytes", "total_size", "totalSize", "total_size_bytes", "totalSizeBytes", "size")
_SNAPSHOT_FILE_COUNT_KEYS = ("file_count", "fileCount", "total_file_count", "totalFileCount", "files")
_SNAPSHOT_DIR_COUNT_KEYS = ("dir_count", "dirCount", "directory_count", "directoryCount", "total_dir_count", "totalDirCount", "dirs")
_SNAPSHOT_STATS_KEYS = ("stats", "summary", "summ", "snapshot", "rootEntry", "root_entry", "root")


def _int_from_mapping(data: dict, keys: tuple[str, ...]) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        try:
            if value not in (None, ""):
                parsed = int(value)
                if parsed > 0:
                    return parsed
        except (TypeError, ValueError):
            continue
    for key in _SNAPSHOT_STATS_KEYS:
        value = data.get(key)
        if isinstance(value, dict):
            parsed = _int_from_mapping(value, keys)
            if parsed > 0:
                return parsed
    return 0


def _directory_size_bytes(row: BackupSourceSnapshotDirectory) -> int:
    value = int(row.size_bytes or 0)
    if value > 0:
        return value
    return _int_from_mapping(row.stats if isinstance(row.stats, dict) else {}, _SNAPSHOT_SIZE_KEYS)


def _directory_file_count(row: BackupSourceSnapshotDirectory) -> int:
    value = int(row.file_count or 0)
    if value > 0:
        return value
    return _int_from_mapping(row.stats if isinstance(row.stats, dict) else {}, _SNAPSHOT_FILE_COUNT_KEYS)


def _directory_dir_count(row: BackupSourceSnapshotDirectory) -> int:
    value = int(row.dir_count or 0)
    if value > 0:
        return value
    return _int_from_mapping(row.stats if isinstance(row.stats, dict) else {}, _SNAPSHOT_DIR_COUNT_KEYS)


class BackupSourceSnapshotDirectorySerializer(serializers.ModelSerializer):
    size_bytes = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()
    dir_count = serializers.SerializerMethodField()

    class Meta:
        model = BackupSourceSnapshotDirectory
        fields = [
            "id",
            "backup_config_dir_id",
            "source_path",
            "path_type",
            "display_name",
            "repository_id",
            "kopia_snapshot_id",
            "status",
            "node_task_id",
            "retry_count",
            "dispatched_at",
            "last_substantive_progress_at",
            "last_progress_snapshot",
            "adopted_late_result",
            "cancel_requested_at",
            "created_at",
            "size_bytes",
            "file_count",
            "dir_count",
            "stats",
            "error_code",
            "error_message",
        ]
        read_only_fields = fields

    def get_size_bytes(self, obj: BackupSourceSnapshotDirectory) -> int:
        return _directory_size_bytes(obj)

    def get_file_count(self, obj: BackupSourceSnapshotDirectory) -> int:
        return _directory_file_count(obj)

    def get_dir_count(self, obj: BackupSourceSnapshotDirectory) -> int:
        return _directory_dir_count(obj)


class BackupSourceSnapshotListSerializer(serializers.ModelSerializer):
    source_display_name = serializers.SerializerMethodField()
    backup_config_name = serializers.SerializerMethodField()
    repository_display_name = serializers.SerializerMethodField()
    kopia_snapshot_count = serializers.SerializerMethodField()
    total_size_bytes = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()
    dir_count = serializers.SerializerMethodField()

    class Meta:
        model = BackupSourceSnapshot
        fields = [
            "id",
            "snapshot_uid",
            "source_type",
            "source_ref_id",
            "source_display_name",
            "backup_config_id",
            "backup_config_name",
            "repository_id",
            "repository_display_name",
            "task_id",
            "task_uuid",
            "trigger_type",
            "status",
            "started_at",
            "finished_at",
            "created_at",
            "directory_count",
            "successful_directory_count",
            "failed_directory_count",
            "kopia_snapshot_count",
            "total_size_bytes",
            "file_count",
            "dir_count",
        ]
        read_only_fields = fields

    def get_source_display_name(self, obj: BackupSourceSnapshot) -> str:
        return str(self.context.get("source_names", {}).get((obj.source_type, obj.source_ref_id), ""))

    def get_backup_config_name(self, obj: BackupSourceSnapshot) -> str:
        return str(self.context.get("backup_config_names", {}).get(obj.backup_config_id, ""))

    def get_repository_display_name(self, obj: BackupSourceSnapshot) -> str:
        return str(self.context.get("repository_names", {}).get(obj.repository_id, ""))

    def get_kopia_snapshot_count(self, obj: BackupSourceSnapshot) -> int:
        return int(obj.successful_directory_count or 0)

    def _available_directories(self, obj: BackupSourceSnapshot) -> list[BackupSourceSnapshotDirectory]:
        rows = list(obj.directories.all())
        return [row for row in rows if row.status == BackupSourceSnapshotDirectory.Status.AVAILABLE]

    def get_total_size_bytes(self, obj: BackupSourceSnapshot) -> int:
        value = int(obj.total_size_bytes or 0)
        if value > 0:
            return value
        return sum(_directory_size_bytes(row) for row in self._available_directories(obj))

    def get_file_count(self, obj: BackupSourceSnapshot) -> int:
        value = int(obj.file_count or 0)
        if value > 0:
            return value
        return sum(_directory_file_count(row) for row in self._available_directories(obj))

    def get_dir_count(self, obj: BackupSourceSnapshot) -> int:
        value = int(obj.dir_count or 0)
        if value > 0:
            return value
        return sum(_directory_dir_count(row) for row in self._available_directories(obj))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get("include_directory_snapshots"):
            data["directories"] = BackupSourceSnapshotDirectorySerializer(
                instance.directories.all(),
                many=True,
            ).data
        return data


class BackupSourceSnapshotDetailSerializer(BackupSourceSnapshotListSerializer):
    directories = BackupSourceSnapshotDirectorySerializer(many=True, read_only=True)

    class Meta(BackupSourceSnapshotListSerializer.Meta):
        fields = BackupSourceSnapshotListSerializer.Meta.fields + [
            "error_code",
            "error_message",
            "metadata",
            "directories",
        ]
        read_only_fields = fields
