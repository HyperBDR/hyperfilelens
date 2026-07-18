"""API permissions for configuration center (platform staff)."""

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsPlatformConfigAdmin(BasePermission):
    """Platform operators (is_staff)."""

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


PLATFORM_CONFIG_PERMISSIONS = [IsAuthenticated, IsPlatformConfigAdmin]
