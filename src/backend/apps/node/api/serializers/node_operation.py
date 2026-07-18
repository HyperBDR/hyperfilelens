"""Serializers for node lifecycle operations."""

from rest_framework import serializers


class NodeOperationStartSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["upgrade", "remove"])
    force = serializers.BooleanField(required=False, default=False)


class NodeOperationBatchPreviewSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["upgrade", "remove"])
    node_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=200,
    )
    max_concurrent = serializers.IntegerField(required=False, min_value=1, max_value=10)
    force = serializers.BooleanField(required=False, default=False)


class NodeOperationBatchStartSerializer(NodeOperationBatchPreviewSerializer):
    pass
