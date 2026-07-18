from __future__ import annotations

from rest_framework import serializers

from apps.protection.models import BackupSourceSnapshot


class BackupTaskSourceInputSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=[("agent", "agent"), ("nas", "nas")])
    source_ref_id = serializers.IntegerField(min_value=1)


class StartBackupTaskSerializer(serializers.Serializer):
    sources = BackupTaskSourceInputSerializer(many=True, required=False)
    source_ids = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
    )
    backup_config_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
    )
    trigger_type = serializers.ChoiceField(
        choices=BackupSourceSnapshot.TriggerType.choices,
        required=False,
        default=BackupSourceSnapshot.TriggerType.MANUAL,
    )
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=True)

    def validate(self, attrs):
        if (
            not attrs.get("sources")
            and not attrs.get("source_ids")
            and not attrs.get("backup_config_ids")
        ):
            raise serializers.ValidationError({"sources": "sources, source_ids or backup_config_ids is required."})
        return attrs


class RetryBackupDirectorySerializer(serializers.Serializer):
    backup_config_dir_id = serializers.IntegerField(min_value=1)
