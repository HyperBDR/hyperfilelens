from rest_framework import serializers

from apps.alert.models import AlertRecord


class AlertRecordSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = AlertRecord
        fields = [
            "id",
            "organization",
            "policy_id",
            "type",
            "severity",
            "status",
            "resource_type",
            "resource_id",
            "resource_name",
            "title",
            "message",
            "current_value",
            "threshold_value",
            "unit",
            "fingerprint",
            "metadata",
            "first_triggered_at",
            "last_triggered_at",
            "acknowledged_at",
            "acknowledged_by",
            "resolved_at",
            "duration_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AlertRecordActionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)
