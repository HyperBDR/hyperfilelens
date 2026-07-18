from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogListSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "organization",
            "organization_name",
            "user",
            "user_display",
            "user_email",
            "user_name",
            "action",
            "resource_type",
            "resource_id",
            "resource_name",
            "target_type",
            "target_id",
            "result",
            "error_message",
            "ip_address",
            "request_method",
            "request_path",
            "correlation_id",
            "request_id",
        ]
        read_only_fields = fields

    def get_user_display(self, obj):
        if obj.user_name:
            return obj.user_name
        if obj.user_email:
            return obj.user_email
        if obj.user_id and obj.user:
            return getattr(obj.user, "username", "") or obj.user_email
        return "System"


class AuditLogDetailSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    user_username = serializers.CharField(source="user.username", read_only=True, allow_null=True)
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_key = serializers.CharField(source="organization.key", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "created_at",
            "organization",
            "organization_name",
            "organization_key",
            "user",
            "user_username",
            "user_display",
            "user_email",
            "user_name",
            "action",
            "target_type",
            "target_id",
            "resource_type",
            "resource_id",
            "resource_name",
            "ip_address",
            "user_agent",
            "details",
            "changes",
            "result",
            "error_message",
            "error_code",
            "request_method",
            "request_path",
            "request_query",
            "request_body",
            "request_id",
            "correlation_id",
            "session_id",
            "metadata",
        ]
        read_only_fields = fields

    def get_user_display(self, obj):
        if obj.user_name:
            return obj.user_name
        if obj.user_email:
            return obj.user_email
        if obj.user_id and obj.user:
            return getattr(obj.user, "username", "") or obj.user_email
        return "System"


AuditLogSerializer = AuditLogDetailSerializer
