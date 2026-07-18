"""Platform Ops user management API."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.users import (
    PlatformOpsResetPasswordSerializer,
    PlatformOpsUserCreateSerializer,
    PlatformOpsUserDetailSerializer,
    PlatformOpsUserListSerializer,
    PlatformOpsUserUpdateSerializer,
)
from apps.platform_ops.api.views._utils import paginated, safe_int
from apps.platform_ops.selectors.internal.users import get_user_detail, list_users
from apps.platform_ops.services.internal.audit import write_platform_audit_log
from apps.platform_ops.services.internal.users import (
    create_platform_user,
    delete_platform_user,
    reset_platform_user_password,
    update_platform_user,
)

User = get_user_model()


class PlatformOpsUserListCreateView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        page = safe_int(request.query_params.get("page"), 1)
        page_size = safe_int(request.query_params.get("page_size"), 20)
        search = request.query_params.get("search", "")

        qs = list_users(search=search)
        total = qs.count()
        offset = (page - 1) * page_size
        page_qs = qs[offset : offset + page_size]
        data = PlatformOpsUserListSerializer(page_qs, many=True).data
        return Response(paginated(data, total=total, page=page, page_size=page_size))

    def post(self, request):
        serializer = PlatformOpsUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        try:
            user = create_platform_user(
                email=payload["email"],
                password=payload["password"],
                first_name=payload.get("first_name", ""),
                last_name=payload.get("last_name", ""),
                is_active=payload.get("is_active", True),
                is_staff=payload.get("is_staff", False),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "fields": {"password": [str(exc)]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        write_platform_audit_log(
            request=request,
            action="user.create",
            target_type="user",
            target_id=str(user.pk),
            details={"email": user.email, "is_staff": user.is_staff},
        )
        detail = get_user_detail(user_id=user.pk)
        return Response(
            PlatformOpsUserDetailSerializer(detail).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformOpsUserDetailView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def _get_user(self, user_id: int):
        user = get_user_detail(user_id=user_id)
        if user is None:
            raise Http404
        return user

    def get(self, request, user_id: int):
        user = self._get_user(user_id)
        return Response(PlatformOpsUserDetailSerializer(user).data)

    def patch(self, request, user_id: int):
        user = self._get_user(user_id)
        serializer = PlatformOpsUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_platform_user(user, **serializer.validated_data)
        write_platform_audit_log(
            request=request,
            action="user.update",
            target_type="user",
            target_id=str(updated.pk),
            details=serializer.validated_data,
        )
        detail = get_user_detail(user_id=updated.pk)
        return Response(PlatformOpsUserDetailSerializer(detail).data)

    def delete(self, request, user_id: int):
        user = self._get_user(user_id)
        try:
            delete_platform_user(user=user, actor=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        write_platform_audit_log(
            request=request,
            action="user.delete",
            target_type="user",
            target_id=str(user_id),
            details={"email": user.email},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformOpsUserResetPasswordView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, user_id: int):
        user = get_user_detail(user_id=user_id)
        if user is None:
            raise Http404
        serializer = PlatformOpsResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reset_platform_user_password(user, serializer.validated_data["password"])
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "fields": {"password": [str(exc)]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        write_platform_audit_log(
            request=request,
            action="user.reset_password",
            target_type="user",
            target_id=str(user.pk),
        )
        return Response({"ok": True})
