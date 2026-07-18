"""Serializers for lifecycle watch polling."""

from rest_framework import serializers

from apps.node.models import Node
from apps.node.services.internal.node_lifecycle import compute_node_lifecycle
from apps.node.services.internal.node_registry import (
    agent_connection_status,
    agent_ws_routable,
)


class NodeLifecycleWatchRequestSerializer(serializers.Serializer):
    node_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=500,
    )


class NodeLifecycleWatchEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    status = serializers.SerializerMethodField()
    routable = serializers.SerializerMethodField()
    version = serializers.CharField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    lifecycle = serializers.SerializerMethodField()

    @staticmethod
    def get_status(obj: Node) -> str:
        return agent_connection_status(obj)

    @staticmethod
    def get_routable(obj: Node) -> bool:
        if obj.role not in (Node.Role.AGENT, Node.Role.PROXY, Node.Role.GATEWAY):
            return obj.status == Node.Status.ONLINE
        return agent_ws_routable(agent_id=obj.id)

    def get_lifecycle(self, obj: Node):
        org = self.context.get("org")
        if org is None or obj.is_deleted:
            return None
        return compute_node_lifecycle(org=org, node=obj)


class NodeLifecycleWatchResponseSerializer(serializers.Serializer):
    nodes = NodeLifecycleWatchEntrySerializer(many=True)
