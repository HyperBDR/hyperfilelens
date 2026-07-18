from rest_framework import serializers

from apps.subscription.models import (
    Entitlement,
    OrganizationSubscription,
    Plan,
    Quota,
    UsageCounter,
)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class OrganizationSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationSubscription
        fields = "__all__"


class EntitlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entitlement
        fields = "__all__"


class QuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quota
        fields = "__all__"


class UsageCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageCounter
        fields = "__all__"

