"""Permissions for instance settings APIs (OSS Admin Console essentials)."""

from rest_framework.permissions import BasePermission

from common.deploy.site import platform_ops_api_allowed


class IsInstanceSettingsStaff(BasePermission):
    """Same gate as Platform Ops listener staff (port 11444)."""

    message = "Instance settings access denied."

    def has_permission(self, request, view):
        return platform_ops_api_allowed(request)
