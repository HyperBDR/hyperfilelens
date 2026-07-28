"""Google OAuth login completion and configuration."""

from __future__ import annotations

from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.auth.token_cookies import issue_auth_tokens_for_user, set_auth_cookies
from apps.iam.services.oauth_error_events import (
    build_oauth_error_redirect,
    consume_oauth_error_event,
)
from apps.iam.services.registration_service import complete_social_user_registration
from common.http.public_api import AnonymousPublicViewMixin


def google_login_url() -> str:
    return reverse("google_login")


def is_google_oauth_enabled() -> bool:
    from apps.platform_ops.services.internal.runtime_settings import google_oauth_ready

    return google_oauth_ready()


def absolute_google_login_url() -> str:
    """Use tenant public URL so non-standard ports (e.g. :11443) are preserved behind nginx."""
    from common.deploy.site import tenant_public_url

    path = google_login_url()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{tenant_public_url().rstrip('/')}{path}"


class GoogleOAuthConfigView(AnonymousPublicViewMixin, APIView):
    """GET /api/v1/auth/google/config"""

    @extend_schema(
        tags=["auth"],
        summary="Google OAuth availability",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        enabled = is_google_oauth_enabled()
        data: dict[str, str | bool] = {"enabled": enabled}
        if enabled:
            data["login_url"] = absolute_google_login_url()
        return Response({"code": "0000", "data": data})


class GoogleOAuthErrorEventConsumeView(AnonymousPublicViewMixin, APIView):
    """POST /api/v1/auth/google/error-events/consume"""

    @extend_schema(
        tags=["auth"],
        summary="Consume a short-lived OAuth error event",
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        reason = consume_oauth_error_event(request.data.get("event_id"))
        response = Response(
            {
                "code": "0000",
                "data": {
                    "verified": reason is not None,
                    "reason": reason or "oauth_failed",
                },
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class GoogleOAuthCallbackView(View):
    """
    Complete Google OAuth: issue JWT cookies and redirect to the SPA.

    Registered at LOGIN_REDIRECT_URL (/accounts/oauth/callback/).
    """

    def get(self, request):
        from common.deploy.site import tenant_public_url

        frontend = tenant_public_url()

        if not is_google_oauth_enabled():
            logout(request)
            return HttpResponseRedirect(
                build_oauth_error_redirect(frontend, "disabled")
            )

        if not request.user.is_authenticated:
            return HttpResponseRedirect(
                build_oauth_error_redirect(frontend, "not_authenticated")
            )

        user = request.user

        if not user.is_active:
            return HttpResponseRedirect(
                build_oauth_error_redirect(frontend, "account_disabled")
            )

        try:
            org = complete_social_user_registration(user)
        except Exception:
            return HttpResponseRedirect(
                build_oauth_error_redirect(frontend, "provision_failed")
            )

        access_token, refresh_token, family_id, membership = issue_auth_tokens_for_user(user, request)
        if membership is None:
            membership_org = org
        else:
            membership_org = membership.organization

        redirect_url = f"{frontend}/auth/oauth/callback?org_key={membership_org.key}"
        response = HttpResponseRedirect(redirect_url)
        set_auth_cookies(response, access_token, refresh_token, family_id)
        # API auth is JWT-only; drop allauth session user to avoid CSRF/session fallback.
        logout(request)
        return response
