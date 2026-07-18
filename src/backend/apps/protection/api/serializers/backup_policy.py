from __future__ import annotations

from rest_framework import serializers

from apps.protection.models import BackupPolicy
from apps.protection.services import (
    backup_policy_related_count,
    backup_policy_retention_summary,
    backup_policy_schedule_summary,
)


class BackupPolicySerializer(serializers.ModelSerializer):
    schedule_summary = serializers.SerializerMethodField()
    retention_summary = serializers.SerializerMethodField()
    related_backup_count = serializers.SerializerMethodField()

    class Meta:
        model = BackupPolicy
        fields = [
            "id",
            "name",
            "is_active",
            "schedule",
            "retention",
            "throttling",
            "error_handling",
            "schedule_summary",
            "retention_summary",
            "related_backup_count",
            "created_at",
            "updated_at",
        ]

    def get_schedule_summary(self, obj: BackupPolicy) -> str:
        return backup_policy_schedule_summary(obj)

    def get_retention_summary(self, obj: BackupPolicy) -> str:
        return backup_policy_retention_summary(obj)

    def get_related_backup_count(self, obj: BackupPolicy) -> int:
        return backup_policy_related_count(policy=obj)


class BackupPolicyWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128, required=False)
    is_active = serializers.BooleanField(required=False)
    schedule = serializers.JSONField(required=False)
    retention = serializers.JSONField(required=False)
    throttling = serializers.JSONField(required=False)
    error_handling = serializers.JSONField(required=False)

    def validate(self, attrs):
        if not self.partial:
            required = ("name", "schedule", "retention", "throttling", "error_handling")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError(
                    {field: "This field is required." for field in missing}
                )
        return attrs


class BulkStateSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    is_active = serializers.BooleanField()


class BulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
