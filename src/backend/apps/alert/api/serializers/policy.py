from rest_framework import serializers

from apps.alert.constants import AlertType, PolicyScope
from apps.alert.models import AlertPolicy
from apps.alert.selectors.interface import notification_channels_for_policy


class AlertPolicySerializer(serializers.ModelSerializer):
    notification_channels = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AlertPolicy
        fields = [
            "id",
            "organization",
            "name",
            "description",
            "type",
            "severity",
            "enabled",
            "resource_type",
            "scope",
            "resource_ids",
            "trigger_rule",
            "recovery_rule",
            "notification_channel_ids",
            "notification_channels",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
            "notification_channels",
        ]

    def validate(self, attrs):
        instance = self.instance
        data = {}
        if instance:
            for field in self.Meta.fields:
                if field in ("notification_channels",):
                    continue
                if hasattr(instance, field):
                    data[field] = getattr(instance, field)
        data.update(attrs)

        alert_type = data.get("type")
        scope = data.get("scope", PolicyScope.SELECTED)
        resource_ids = data.get("resource_ids") or []
        resource_type = data.get("resource_type")
        trigger_rule = data.get("trigger_rule") or {}

        if not resource_type:
            raise serializers.ValidationError({"resource_type": "This field is required."})

        if (
            scope == PolicyScope.SELECTED
            and alert_type != AlertType.EVENT
            and resource_type != "system"
            and not resource_ids
        ):
            raise serializers.ValidationError(
                {"resource_ids": "Required when scope is selected."}
            )

        required_by_type = {
            AlertType.METRIC: [
                "metric_key",
                "operator",
                "threshold",
                "duration_seconds",
                "evaluation_interval_seconds",
            ],
            AlertType.AVAILABILITY: ["check_type", "timeout_seconds", "duration_seconds"],
            AlertType.TASK: ["task_type", "event_type"],
            AlertType.EVENT: ["event_category", "event_types"],
            AlertType.SYSTEM: ["check_type", "duration_seconds"],
        }
        missing = [
            key
            for key in required_by_type.get(alert_type, [])
            if trigger_rule.get(key) in (None, "", [])
        ]
        if missing:
            raise serializers.ValidationError(
                {"trigger_rule": f"Missing required fields: {', '.join(missing)}"}
            )

        org = self.context.get("organization")
        if org is None and instance is not None:
            org = instance.organization
        channel_ids = data.get("notification_channel_ids") or []
        if org is not None and channel_ids:
            from apps.notification.models import NotificationChannel

            int_ids = []
            for raw in channel_ids:
                try:
                    int_ids.append(int(raw))
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        {"notification_channel_ids": f"Invalid channel id: {raw}"}
                    )
            found = set(
                NotificationChannel.objects.filter(
                    organization=org, id__in=int_ids, is_active=True
                ).values_list("id", flat=True)
            )
            missing_ids = [cid for cid in int_ids if cid not in found]
            if missing_ids:
                raise serializers.ValidationError(
                    {
                        "notification_channel_ids": (
                            f"Unknown or inactive channels: {missing_ids}"
                        )
                    }
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        org = self.context.get("organization")
        if org is not None:
            validated_data["organization"] = org
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user.id
        return super().create(validated_data)

    def get_notification_channels(self, obj):
        org = obj.organization
        return notification_channels_for_policy(obj, org)


class BulkPolicyStateSerializer(serializers.Serializer):
    """Request payload for bulk enable/disable of alert policies."""

    ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=500,
    )
    enabled = serializers.BooleanField()


class BulkPolicyDeleteSerializer(serializers.Serializer):
    """Request payload for bulk delete of alert policies."""

    ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=500,
    )
