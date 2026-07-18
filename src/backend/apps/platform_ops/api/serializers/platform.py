"""Platform Ops API serializers for health, runtime, licensing, etc."""

from __future__ import annotations

from rest_framework import serializers

from apps.alert.models import AlertRecord
from apps.notification.models import NotificationLog
from apps.platform_ops.models import PlatformAuditLog
from apps.subscription.models import License, OrganizationSubscription, Plan
from apps.task.models import Task


class PlatformAlertRowSerializer(serializers.ModelSerializer):
    organization_key = serializers.CharField(source="organization.key", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = AlertRecord
        fields = [
            "id",
            "organization_id",
            "organization_key",
            "organization_name",
            "title",
            "severity",
            "status",
            "resource_type",
            "resource_name",
            "last_triggered_at",
            "created_at",
        ]


class PlatformTaskRowSerializer(serializers.ModelSerializer):
    organization_key = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "task_uuid",
            "organization_id",
            "organization_key",
            "organization_name",
            "task_type",
            "status",
            "display_name",
            "error_message",
            "finished_at",
            "created_at",
        ]

    def _org_info(self, obj: Task) -> dict[str, str]:
        org_map = self.context.get("org_map") or {}
        return org_map.get(obj.organization_id, {})

    def get_organization_key(self, obj: Task) -> str:
        return self._org_info(obj).get("key", "")

    def get_organization_name(self, obj: Task) -> str:
        return self._org_info(obj).get("name", "")


class PlatformNotificationRowSerializer(serializers.ModelSerializer):
    organization_key = serializers.CharField(source="organization.key", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    channel_name = serializers.CharField(source="channel.name", read_only=True, default="")

    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "organization_id",
            "organization_key",
            "organization_name",
            "channel_name",
            "status",
            "error_message",
            "sent_at",
        ]


class PlatformNodeRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    organization_id = serializers.IntegerField()
    organization_key = serializers.CharField()
    organization_name = serializers.CharField()
    hostname = serializers.CharField()
    role = serializers.CharField()
    status = serializers.CharField()
    agent_version = serializers.CharField(allow_blank=True)
    updated_at = serializers.DateTimeField(allow_null=True)


class PlatformAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default="")

    class Meta:
        model = PlatformAuditLog
        fields = [
            "id",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "org_key",
            "details",
            "ip_address",
            "result",
            "created_at",
        ]


class PlatformOrgCreateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=200)
    owner_user_id = serializers.IntegerField(min_value=1)
    is_active = serializers.BooleanField(default=True)


class PlatformOrgUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    is_active = serializers.BooleanField(required=False)


class PlatformPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "key", "name", "is_active", "spec", "created_at", "updated_at"]


class PlatformSubscriptionSerializer(serializers.ModelSerializer):
    organization_key = serializers.CharField(source="organization.key", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    plan_key = serializers.CharField(source="plan.key", read_only=True)

    class Meta:
        model = OrganizationSubscription
        fields = [
            "id",
            "organization_id",
            "organization_key",
            "organization_name",
            "plan_id",
            "plan_key",
            "status",
            "started_at",
            "ends_at",
            "overrides",
            "created_at",
            "updated_at",
        ]


class PlatformLicenseRowSerializer(serializers.ModelSerializer):
    organization_key = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()

    class Meta:
        model = License
        fields = [
            "id",
            "organization_id",
            "organization_key",
            "organization_name",
            "license_key",
            "status",
            "expires_at",
            "created_at",
        ]

    def get_organization_key(self, obj):
        return getattr(obj, "organization_key", None) or getattr(
            getattr(obj, "organization", None),
            "key",
            None,
        )

    def get_organization_name(self, obj):
        return getattr(obj, "organization_name", None) or getattr(
            getattr(obj, "organization", None),
            "name",
            None,
        )


class PlatformQuotaUsageSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    organization_key = serializers.CharField()
    organization_name = serializers.CharField()
    key = serializers.CharField()
    limit = serializers.IntegerField()
    unit = serializers.CharField()
    used = serializers.IntegerField()


class PlatformQuotaPatchSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField(min_value=1)
    key = serializers.CharField(max_length=120)
    limit = serializers.IntegerField(min_value=0)
