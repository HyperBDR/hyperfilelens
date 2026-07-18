from rest_framework import serializers

from apps.node.services.internal.node_registry import agent_connection_status
from apps.source.models import SourceResource
from apps.source.services.internal.nas_display import connection_summary_for_resource
from apps.source.services.internal.validators import validate_resource_payload


class SourceResourceSerializer(serializers.ModelSerializer):
    resource_type_display = serializers.CharField(
        source="get_resource_type_display", read_only=True
    )
    mount_status_display = serializers.CharField(
        source="get_mount_status_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    bound_node_name = serializers.CharField(source="bound_node.name", read_only=True, allow_null=True)
    bound_node_status = serializers.SerializerMethodField()
    requires_mount = serializers.SerializerMethodField()
    usage_percentage = serializers.SerializerMethodField()
    connection_summary = serializers.SerializerMethodField()

    class Meta:
        model = SourceResource
        fields = [
            "id",
            "organization",
            "name",
            "description",
            "resource_type",
            "resource_type_display",
            "config",
            "credentials",
            "bound_node",
            "bound_node_name",
            "bound_node_status",
            "mount_status",
            "mount_status_display",
            "mount_point",
            "mount_error",
            "status",
            "status_display",
            "status_message",
            "last_connection_test",
            "connection_test_result",
            "total_size",
            "used_size",
            "free_size",
            "usage_percentage",
            "file_count",
            "requires_mount",
            "connection_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "mount_status",
            "mount_point",
            "mount_error",
            "last_connection_test",
            "connection_test_result",
            "total_size",
            "used_size",
            "free_size",
            "file_count",
            "created_at",
            "updated_at",
        ]

    def get_bound_node_status(self, obj):
        node = obj.bound_node
        if node is None:
            return None
        return agent_connection_status(node)

    def get_requires_mount(self, obj):
        return obj.requires_mount

    def get_usage_percentage(self, obj):
        if not obj.total_size:
            return 0
        return round((obj.used_size / obj.total_size) * 100, 2)

    def get_connection_summary(self, obj):
        return connection_summary_for_resource(
            resource_type=obj.resource_type,
            config=obj.config or {},
        )


class SourceResourceListSerializer(SourceResourceSerializer):
    class Meta(SourceResourceSerializer.Meta):
        fields = [
            "id",
            "name",
            "description",
            "resource_type",
            "resource_type_display",
            "config",
            "bound_node",
            "bound_node_name",
            "bound_node_status",
            "mount_status",
            "mount_point",
            "status",
            "status_display",
            "total_size",
            "used_size",
            "free_size",
            "usage_percentage",
            "file_count",
            "connection_summary",
            "requires_mount",
            "last_connection_test",
            "created_at",
            "updated_at",
        ]


class SourceResourceWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    resource_type = serializers.CharField(max_length=20)
    config = serializers.JSONField(required=False, default=dict)
    credentials = serializers.JSONField(required=False, default=dict)
    bound_node = serializers.IntegerField(required=False, allow_null=True)
    bound_node_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        validate_resource_payload(
            resource_type=attrs.get("resource_type", ""),
            config=attrs.get("config") or {},
            credentials=attrs.get("credentials") or {},
        )
        return attrs


class SourceResourceUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    resource_type = serializers.CharField(max_length=20, required=False)
    config = serializers.JSONField(required=False)
    credentials = serializers.JSONField(required=False)
    bound_node = serializers.IntegerField(required=False, allow_null=True)
    bound_node_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True)
