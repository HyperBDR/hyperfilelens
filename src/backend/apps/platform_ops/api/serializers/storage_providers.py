"""Input serializers for Object Storage Provider Catalog operations."""

from __future__ import annotations

from rest_framework import serializers


class ProviderCatalogContentSerializer(serializers.Serializer):
    content = serializers.CharField(trim_whitespace=False)


class ProviderCatalogApplySerializer(ProviderCatalogContentSerializer):
    input_checksum = serializers.RegexField(r"^[0-9a-f]{64}$")
    review_token = serializers.CharField(max_length=16384, trim_whitespace=False)
    risk_confirmations = serializers.ListField(
        child=serializers.CharField(max_length=300),
        allow_empty=True,
    )


class ProviderCatalogResetSerializer(serializers.Serializer):
    reset_token = serializers.CharField(max_length=16384, trim_whitespace=False)


class ProviderValidationCredentialSerializer(serializers.Serializer):
    access_key_id = serializers.CharField(
        max_length=256,
        trim_whitespace=True,
        write_only=True,
    )
    secret_access_key = serializers.CharField(
        max_length=512,
        trim_whitespace=False,
        write_only=True,
    )


class ProviderValidationRunCreateSerializer(ProviderValidationCredentialSerializer):
    provider_id = serializers.RegexField(r"^[a-z][a-z0-9_-]{0,49}$")
    region_ids = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=10,
        allow_empty=False,
    )
    candidate_config = serializers.JSONField(required=True)

    def validate_region_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Region IDs must be unique.")
        return value
