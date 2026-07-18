from __future__ import annotations

from rest_framework import serializers

from apps.protection.models import FileFilterRule
from apps.protection.services import file_filter_related_count, file_filter_summary


class FileFilterRuleSerializer(serializers.ModelSerializer):
    summary = serializers.SerializerMethodField()
    related_backup_count = serializers.SerializerMethodField()

    class Meta:
        model = FileFilterRule
        fields = [
            "id",
            "name",
            "is_active",
            "ignore_patterns",
            "large_file_limit_enabled",
            "large_file_bytes_max",
            "ignore_cache_directories",
            "current_filesystem_only",
            "summary",
            "related_backup_count",
            "created_at",
            "updated_at",
        ]

    def get_summary(self, obj: FileFilterRule) -> str:
        return file_filter_summary(obj)

    def get_related_backup_count(self, obj: FileFilterRule) -> int:
        return file_filter_related_count(rule=obj)


class FileFilterRuleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128, required=False)
    is_active = serializers.BooleanField(required=False)
    ignore_patterns = serializers.CharField(required=False, allow_blank=True)
    large_file_limit_enabled = serializers.BooleanField(required=False)
    large_file_bytes_max = serializers.IntegerField(required=False, min_value=0)
    ignore_cache_directories = serializers.BooleanField(required=False)
    current_filesystem_only = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not self.partial and "name" not in attrs:
            raise serializers.ValidationError({"name": "This field is required."})
        return attrs
