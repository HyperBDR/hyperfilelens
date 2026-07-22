"""Serializers for ``NodeToken``."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.node import conf as node_conf
from apps.node.models import Node, NodeToken
from common.deploy.site import enrollment_tls_verify


class NodeTokenSerializer(serializers.ModelSerializer):
    tls_verify = serializers.SerializerMethodField()

    class Meta:
        model = NodeToken
        fields = [
            "id",
            "organization",
            "token",
            "role",
            "note",
            "is_active",
            "created_at",
            "updated_at",
            "expires_at",
            "used_at",
            "gateway_scope",
            "tls_verify",
            "is_deleted",
            "deleted_at",
        ]
        read_only_fields = [
            "id",
            "token",
            "created_at",
            "updated_at",
            "used_at",
            "is_deleted",
            "deleted_at",
        ]

    def get_tls_verify(self, _instance: NodeToken) -> bool:
        """Return the deployment TLS policy used by generated install commands."""
        return enrollment_tls_verify()


class NodeTokenCreateSerializer(serializers.ModelSerializer):
    """Create enrollment token (organization from active ``X-Org-Key`` / ``?org=``)."""

    org = serializers.SlugField(required=False, write_only=True)

    class Meta:
        model = NodeToken
        fields = ["org", "role", "note", "expires_at", "is_active", "gateway_scope"]
        extra_kwargs = {
            "note": {"required": False, "default": ""},
            "is_active": {"required": False, "default": True},
            "expires_at": {"required": False},
            "gateway_scope": {"required": False, "default": ""},
        }

    def validate_role(self, value: str) -> str:
        if value not in dict(Node.Role.choices):
            raise serializers.ValidationError("invalid role")
        return value

    def create(self, validated_data):
        if "expires_at" not in validated_data:
            ttl = node_conf.ENROLLMENT_TOKEN_TTL_SECONDS
            if ttl > 0:
                validated_data["expires_at"] = timezone.now() + timedelta(seconds=ttl)
        return super().create(validated_data)
