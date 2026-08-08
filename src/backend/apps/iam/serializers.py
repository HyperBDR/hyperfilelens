"""
IAM serializers.
"""

from django.contrib.auth import get_user_model

from rest_framework import serializers

from apps.iam.models import Membership, Organization, PersonalApiKey
from apps.iam.services.membership_service import (
    MembershipPolicyError,
    assert_role_assignable,
)


User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    owner_email = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "key", "name", "is_active", "created_at", "updated_at", "owner_email", "member_count"]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "key": {"required": False},
        }

    def get_owner_email(self, obj):
        from common.extension_spi import get_authz_provider

        provider = get_authz_provider()
        if provider is not None:
            email = provider.resolve_owner_email(obj)
            if email:
                return email
        # Community: sole / first active affiliation.
        owner = (
            obj.memberships.filter(is_active=True)
            .select_related("user")
            .order_by("id")
            .first()
        )
        return owner.user.email if owner else None

    def get_member_count(self, obj):
        count = getattr(obj, "member_count", None)
        if count is not None:
            return count
        return obj.memberships.filter(is_active=True).count()


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "organization",
            "organization_name",
            "user",
            "user_email",
            "user_username",
            "role",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "organization"]

    def get_role(self, obj):
        from apps.iam.services.membership_service import authoritative_role

        return authoritative_role(obj)

    def validate_role(self, value):
        assert_role_assignable(value)
        return value

    def to_internal_value(self, data):
        # role is SerializerMethodField on output; accept writable role on input.
        ret = super().to_internal_value(data)
        if "role" in data:
            role = data.get("role")
            self.validate_role(role)
            ret["role"] = role
        return ret

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        from apps.iam.services.membership_service import (
            active_owner_count,
            authoritative_role,
        )

        if instance is None:
            return attrs
        if authoritative_role(instance) == Membership.Role.OWNER:
            if "role" in attrs and attrs["role"] != Membership.Role.OWNER:
                raise serializers.ValidationError(
                    {"role": "Owner role cannot be changed via membership API."}
                )
        if attrs.get("is_active") is False and instance.is_active:
            if active_owner_count(instance.organization, exclude_pk=instance.pk) < 1:
                raise serializers.ValidationError(
                    {"is_active": "Cannot deactivate the organization owner."}
                )
        return attrs

    def create(self, validated_data):
        from apps.iam.services.membership_service import create_org_membership

        organization = validated_data["organization"]
        try:
            return create_org_membership(
                organization=organization,
                user=validated_data["user"],
                role=validated_data.get("role", Membership.Role.OPERATOR),
                is_active=validated_data.get("is_active", True),
            )
        except MembershipPolicyError as exc:
            raise serializers.ValidationError(exc.detail) from exc

    def update(self, instance, validated_data):
        from apps.iam.services.membership_service import update_org_membership

        try:
            return update_org_membership(instance, **validated_data)
        except MembershipPolicyError as exc:
            raise serializers.ValidationError(exc.detail) from exc


class PersonalApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalApiKey
        fields = ["id", "name", "token", "is_active", "created_at"]
        read_only_fields = ["id", "token", "created_at"]
