"""Platform Ops API permissions."""

from rest_framework.permissions import BasePermission

from common.deploy.site import platform_ops_api_allowed


class IsPlatformOpsStaff(BasePermission):
    """Allow Platform Ops only on the operations listener for permitted staff."""

    message = "Platform Ops access denied."

    def has_permission(self, request, view):
        return platform_ops_api_allowed(request)
