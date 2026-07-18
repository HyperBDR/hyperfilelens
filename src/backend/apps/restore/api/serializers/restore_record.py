from __future__ import annotations

from rest_framework import serializers

from apps.restore.models import RestoreRecord, RestoreRecordItem
from apps.task.models import Task


class RestoreRecordTaskSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["status", "progress", "started_at", "finished_at"]
        read_only_fields = fields


class RestoreRecordItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestoreRecordItem
        fields = [
            "id",
            "source_snapshot_directory_id",
            "backup_config_dir_id",
            "repository_id",
            "kopia_snapshot_id",
            "source_path",
            "selected_paths",
            "target_path",
            "conflict_mode",
            "status",
            "node_task_id",
            "last_progress_snapshot",
            "result_payload",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RestoreRecordSerializer(serializers.ModelSerializer):
    items = RestoreRecordItemSerializer(many=True, read_only=True)
    source_snapshot_uid = serializers.SerializerMethodField()
    task_summary = serializers.SerializerMethodField()

    def get_source_snapshot_uid(self, obj: RestoreRecord) -> str:
        snapshot_uid_by_id = self.context.get("snapshot_uid_by_id")
        if not isinstance(snapshot_uid_by_id, dict):
            return ""
        return str(snapshot_uid_by_id.get(obj.source_snapshot_id, ""))

    def get_task_summary(self, obj: RestoreRecord) -> dict | None:
        task_by_uuid = self.context.get("task_by_uuid")
        if not isinstance(task_by_uuid, dict):
            return None
        task = task_by_uuid.get(str(obj.task_uuid))
        if task is None:
            return None
        return RestoreRecordTaskSummarySerializer(task).data

    class Meta:
        model = RestoreRecord
        fields = [
            "id",
            "restore_uid",
            "source_mode",
            "plan_id",
            "task_id",
            "task_uuid",
            "source_type",
            "source_ref_id",
            "backup_config_id",
            "source_snapshot_id",
            "source_snapshot_uid",
            "target_type",
            "target_ref_id",
            "target_path",
            "scope",
            "conflict_mode",
            "request_payload",
            "expanded_payload",
            "created_by_id",
            "created_at",
            "updated_at",
            "items",
            "task_summary",
        ]
        read_only_fields = fields


class RestoreRecordItemCreateSerializer(serializers.Serializer):
    source_snapshot_directory_id = serializers.IntegerField(min_value=1)
    selected_paths = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        required=False,
        default=list,
    )
    target_path = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    conflict_mode = serializers.ChoiceField(
        choices=RestoreRecord.ConflictMode.choices,
        required=False,
    )


class RestoreRecordCreateSerializer(serializers.Serializer):
    source_snapshot_id = serializers.IntegerField(min_value=1)
    source_type = serializers.ChoiceField(choices=RestoreRecord.EndpointType.choices)
    source_ref_id = serializers.IntegerField(min_value=1)
    target_type = serializers.ChoiceField(choices=RestoreRecord.EndpointType.choices)
    target_ref_id = serializers.IntegerField(min_value=1)
    target_path = serializers.CharField(max_length=1000)
    scope = serializers.ChoiceField(choices=RestoreRecord.Scope.choices)
    conflict_mode = serializers.ChoiceField(choices=RestoreRecord.ConflictMode.choices)
    items = RestoreRecordItemCreateSerializer(many=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=128)


class RestoreCreateResultSerializer(serializers.Serializer):
    restore_record_id = serializers.IntegerField()
    restore_uid = serializers.CharField()
    task_id = serializers.IntegerField()
    task_uuid = serializers.UUIDField()
    status = serializers.CharField()
    source_snapshot_id = serializers.IntegerField()
    item_count = serializers.IntegerField()
    items = RestoreRecordItemSerializer(many=True)
