from __future__ import annotations

from rest_framework import serializers


class BackupTargetValidationSourceSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=128)
    source_type = serializers.ChoiceField(choices=[("agent", "agent"), ("nas", "nas")])
    source_ref_id = serializers.IntegerField(min_value=1)
    repository_id = serializers.IntegerField(min_value=1)
    repository_endpoint_type = serializers.ChoiceField(
        choices=[("external", "external"), ("internal", "internal")],
        required=False,
        default="external",
    )


class BackupTargetValidationSerializer(serializers.Serializer):
    sources = BackupTargetValidationSourceSerializer(
        many=True,
        allow_empty=False,
        max_length=500,
    )

    def validate_sources(self, value):
        keys = [str(item["key"]) for item in value]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("Source row keys must be unique.")
        return value
