from __future__ import annotations

from rest_framework import serializers

from apps.restore.models import RestorePlan


class RestorePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestorePlan
        fields = [
            "id",
            "backup_config_id",
            "backup_config_dir_id",
            "scope",
            "source_type",
            "source_ref_id",
            "source_path",
            "target_type",
            "target_ref_id",
            "restore_dir",
            "conflict_mode",
            "enabled",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RestorePlanWriteSerializer(serializers.Serializer):
    backup_config_id = serializers.IntegerField(min_value=1)
    backup_config_dir_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    scope = serializers.ChoiceField(choices=RestorePlan.Scope.choices, required=False, default=RestorePlan.Scope.PATHS)
    source_type = serializers.ChoiceField(choices=RestorePlan.EndpointType.choices)
    source_ref_id = serializers.IntegerField(min_value=1)
    source_path = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    target_type = serializers.ChoiceField(choices=RestorePlan.EndpointType.choices)
    target_ref_id = serializers.IntegerField(min_value=1)
    restore_dir = serializers.CharField(max_length=1000)
    conflict_mode = serializers.ChoiceField(choices=RestorePlan.ConflictMode.choices)
    enabled = serializers.BooleanField(required=False, default=True)
    sort_order = serializers.IntegerField(required=False, default=0)


class RestorePlanPatchSerializer(serializers.Serializer):
    backup_config_id = serializers.IntegerField(min_value=1, required=False)
    backup_config_dir_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    scope = serializers.ChoiceField(choices=RestorePlan.Scope.choices, required=False)
    source_type = serializers.ChoiceField(choices=RestorePlan.EndpointType.choices, required=False)
    source_ref_id = serializers.IntegerField(min_value=1, required=False)
    source_path = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    target_type = serializers.ChoiceField(choices=RestorePlan.EndpointType.choices, required=False)
    target_ref_id = serializers.IntegerField(min_value=1, required=False)
    restore_dir = serializers.CharField(max_length=1000, required=False)
    conflict_mode = serializers.ChoiceField(choices=RestorePlan.ConflictMode.choices, required=False)
    enabled = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(required=False)


class RestorePlanRunSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=128)
    source_snapshot_id = serializers.IntegerField(required=False, min_value=1)


class RestorePlanBatchRunSerializer(serializers.Serializer):
    backup_config_id = serializers.IntegerField(min_value=1)
    target_type = serializers.ChoiceField(choices=RestorePlan.EndpointType.choices)
    target_ref_id = serializers.IntegerField(min_value=1)
    restore_dir = serializers.CharField(max_length=1000)
    conflict_mode = serializers.ChoiceField(choices=RestorePlan.ConflictMode.choices)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=128)
    source_snapshot_id = serializers.IntegerField(required=False, min_value=1)


class RestorePlanSourceRunSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=RestorePlan.EndpointType.choices)
    source_ref_id = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=128)
    source_snapshot_id = serializers.IntegerField(required=False, min_value=1)
