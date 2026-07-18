"""Serializers for ``Node``."""

from rest_framework import serializers

from apps.node.models import Node
from apps.node.services.internal.node_registry import (
    agent_connection_status,
    agent_ws_routable,
)


class NodeSerializer(serializers.ModelSerializer):
    """Console REST representation of a registered Agent node."""

    agent_control_ws_path = serializers.SerializerMethodField(read_only=True)
    status = serializers.SerializerMethodField()
    routable = serializers.SerializerMethodField()
    lifecycle = serializers.SerializerMethodField(read_only=True)
    workload = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Node
        fields = [
            "id",
            "organization",
            "name",
            "role",
            "version",
            "os_name",
            "ip_address",
            "status",
            "routable",
            "last_seen_at",
            "metadata",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
            "agent_control_ws_path",
            "lifecycle",
            "workload",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_deleted",
            "deleted_at",
            "agent_control_ws_path",
            "lifecycle",
            "workload",
        ]

    @staticmethod
    def get_agent_control_ws_path(_obj: Node) -> str:
        return "/ws/node/agent/"

    @staticmethod
    def get_status(obj: Node) -> str:
        return agent_connection_status(obj)

    @staticmethod
    def get_routable(obj: Node) -> bool:
        if obj.role not in (Node.Role.AGENT, Node.Role.PROXY, Node.Role.GATEWAY):
            return obj.status == Node.Status.ONLINE
        return agent_ws_routable(agent_id=obj.id)

    def get_lifecycle(self, obj: Node):
        enrichments = self.context.get("enrichments") or {}
        row = enrichments.get(obj.id)
        if isinstance(row, dict):
            return row.get("lifecycle")
        return None

    def get_workload(self, obj: Node):
        enrichments = self.context.get("enrichments") or {}
        row = enrichments.get(obj.id)
        if isinstance(row, dict):
            return row.get("workload")
        return None


class NodeHeartbeatSerializer(serializers.Serializer):
    """Agent HTTP heartbeat payload (``NodeViewSet.heartbeat``)."""

    node_id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=Node.Role.choices)
    version = serializers.CharField(required=False, allow_blank=True)
    os_name = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
