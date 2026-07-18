"""
Serializers for runtime configuration.
"""

from rest_framework import serializers

from apps.configuration.models import GlobalConfig
from apps.configuration.services.internal.registry import registry_by_key
from apps.configuration.services.internal.validation import (
    validate_config_key,
    validate_value_for_type,
)


class GlobalConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalConfig
        fields = [
            "id",
            "key",
            "scope",
            "tenant_key",
            "category",
            "value_type",
            "value",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate_key(self, value: str) -> str:
        validate_config_key(value)
        return str(value).strip()

    def validate(self, attrs):
        value = attrs.get("value", getattr(self.instance, "value", None))
        value_type = attrs.get(
            "value_type",
            getattr(self.instance, "value_type", GlobalConfig.ValueType.STRING),
        )
        if value is not None and value_type:
            validate_value_for_type(value=value, value_type=value_type)

        key = attrs.get("key", getattr(self.instance, "key", None))
        if key and key in registry_by_key() and not attrs.get("category"):
            attrs.setdefault("category", registry_by_key()[key].category)
        return attrs


class GlobalConfigListSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalConfig
        fields = [
            "id",
            "key",
            "scope",
            "tenant_key",
            "category",
            "value_type",
            "value",
            "description",
            "is_active",
            "updated_at",
        ]


class ConfigKeySpecSerializer(serializers.Serializer):
    key = serializers.CharField()
    category = serializers.CharField()
    value_type = serializers.CharField()
    description = serializers.CharField()
    owning_app = serializers.CharField()
