"""Deploy profile API for runtime frontend configuration."""

from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.auth.authentication import OptionalJWTAuthenticationFromCookies
from common.deploy.site import (
    admin_console_entry_visible,
    admin_console_public_url,
    default_landing_path,
    platform_ops_access_allowed,
    resolve_site_role,
    tenant_public_url,
)


class DeployProfileView(APIView):
    """
    GET /api/v1/meta/deploy-profile

    Anonymous-safe fields; authenticated users receive Platform Ops visibility.
    """

    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthenticationFromCookies]

    def get(self, request):
        from apps.platform_ops.services.internal.runtime_settings import (
            platform_ops_enabled,
            registration_enabled,
            self_service_password_reset_enabled,
        )

        site_role = resolve_site_role(request)
        payload = {
            "site_role": site_role,
            "registration_enabled": registration_enabled() if site_role == "tenant" else False,
            "platform_ops_enabled": platform_ops_enabled(),
            "self_service_password_reset": self_service_password_reset_enabled(),
            "tenant_public_url": tenant_public_url(),
            "admin_console_url": admin_console_public_url(request),
            "landing_path": default_landing_path(request),
            "admin_console_entry_visible": False,
            "platform_ops_access_allowed": False,
        }

        if request.user and request.user.is_authenticated:
            payload["is_staff"] = bool(request.user.is_staff)
            payload["admin_console_entry_visible"] = admin_console_entry_visible(
                request,
            )
            payload["platform_ops_access_allowed"] = platform_ops_access_allowed(
                request,
            )
            from apps.platform_ops.constants import SUPPORT_SESSION_KEY

            support_key = request.session.get(SUPPORT_SESSION_KEY)
            if support_key and request.user.is_staff:
                payload["support_org_key"] = support_key
            else:
                payload["support_org_key"] = None
        else:
            payload["is_staff"] = False
            payload["support_org_key"] = None

        return Response(payload)
