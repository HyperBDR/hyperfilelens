"""Platform Ops organization serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.iam.models import Membership, Organization
from apps.platform_ops.selectors.internal.orgs import owner_email_for_org


class PlatformOpsOrganizationListSerializer(serializers.ModelSerializer):
    owner_email = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "key",
            "name",
            "is_active",
            "owner_email",
            "member_count",
            "created_at",
            "updated_at",
        ]

    @staticmethod
    def get_owner_email(obj):
        email = getattr(obj, "_owner_email", None)
        if email:
            return email
        return owner_email_for_org(obj)


class PlatformOpsOrgMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_display_name = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "user_id",
            "user_email",
            "user_display_name",
            "role",
            "is_active",
            "created_at",
        ]

    @staticmethod
    def get_user_display_name(obj):
        user = obj.user
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return name or user.email or user.username or str(user.pk)


class PlatformOpsOrganizationDetailSerializer(PlatformOpsOrganizationListSerializer):
    memberships = PlatformOpsOrgMembershipSerializer(many=True, read_only=True)

    class Meta(PlatformOpsOrganizationListSerializer.Meta):
        fields = PlatformOpsOrganizationListSerializer.Meta.fields + ["memberships"]
