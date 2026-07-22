"""Platform Ops user list/detail serializers."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from apps.iam.models import Membership

User = get_user_model()


class PlatformOpsMembershipSerializer(serializers.ModelSerializer):
    organization_key = serializers.CharField(source="organization.key", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "organization",
            "organization_key",
            "organization_name",
            "role",
            "is_active",
            "created_at",
        ]


class PlatformOpsUserListSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    membership_count = serializers.IntegerField(read_only=True)
    account_type = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    registered_at = serializers.SerializerMethodField()
    last_login_ip = serializers.SerializerMethodField()
    has_usable_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "is_active",
            "is_staff",
            "account_type",
            "date_joined",
            "last_login",
            "registered_at",
            "last_login_ip",
            "has_usable_password",
            "membership_count",
            "organization",
        ]

    @staticmethod
    def get_display_name(obj):
        name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        return name or obj.email or obj.username or str(obj.pk)

    @staticmethod
    def get_account_type(obj):
        return "administrator" if obj.is_staff else "customer"

    @staticmethod
    def get_organization(obj):
        memberships = getattr(obj, "platform_memberships", [])
        membership = next(
            (
                row
                for row in memberships
                if row.role == Membership.Role.OWNER
            ),
            memberships[0] if memberships else None,
        )
        if membership is None:
            return None
        org = membership.organization
        return {
            "id": org.id,
            "key": org.key,
            "name": org.name,
            "is_active": org.is_active,
        }

    @staticmethod
    def get_registered_at(obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "registered_at", None)

    @staticmethod
    def get_last_login_ip(obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "last_login_ip", "")

    @staticmethod
    def get_has_usable_password(obj):
        return obj.has_usable_password()


class PlatformOpsUserDetailSerializer(PlatformOpsUserListSerializer):
    memberships = PlatformOpsMembershipSerializer(many=True, read_only=True)

    class Meta(PlatformOpsUserListSerializer.Meta):
        fields = PlatformOpsUserListSerializer.Meta.fields + ["memberships"]


class PlatformOpsUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)
    is_staff = serializers.BooleanField(default=False)
    organization_name = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
    )

    @staticmethod
    def validate_email(value: str) -> str:
        email = value.strip().lower()
        if User.objects.filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        ).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return email


class PlatformOpsUserUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)


class PlatformOpsResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
