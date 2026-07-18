"""
Captcha views for login protection.
"""

import logging
import time

from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.http.public_api import AnonymousPublicViewMixin

from apps.iam.services import (
    CAPTCHA_EXPIRE_SECONDS,
    generate_captcha_id,
    generate_captcha_text,
    generate_svg_captcha,
    get_captcha_provider,
    save_captcha,
    validate_captcha,
)
from apps.iam.services.turnstile_service import get_client_ip


from common.i18n.client_lang import activate_request_language

logger = logging.getLogger(__name__)

TURNSTILE_INFRA_FALLBACK_REASONS = frozenset({
    "widget_error",
    "script_load_failed",
    "config_unavailable",
})


class CaptchaConfigView(AnonymousPublicViewMixin, APIView):
    """
    Public captcha mode for auth pages.
    GET /api/v1/auth/captcha-config
    """

    @extend_schema(
        tags=["auth"],
        summary="Get captcha provider configuration",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        activate_request_language(request)
        provider = get_captcha_provider()
        data: dict[str, str | bool] = {
            "captcha_provider": provider,
            "image_fallback_enabled": provider == "turnstile",
        }
        if provider == "turnstile":
            from apps.platform_ops.services.internal.runtime_settings import turnstile_site_key

            data["turnstile_site_key"] = turnstile_site_key()
        return Response(
            {"code": "0000", "data": data},
            status=status.HTTP_200_OK,
        )


class CaptchaFallbackReportView(AnonymousPublicViewMixin, APIView):
    """
    Best-effort client report when Turnstile degrades to image captcha due to infra/config issues.
    POST /api/v1/auth/captcha-fallback-report
    """

    @extend_schema(
        tags=["auth"],
        summary="Report Turnstile infrastructure fallback",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": sorted(TURNSTILE_INFRA_FALLBACK_REASONS),
                    },
                },
                "required": ["reason"],
            }
        },
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        activate_request_language(request)
        reason = str(request.data.get("reason", "") or "").strip()
        if reason not in TURNSTILE_INFRA_FALLBACK_REASONS:
            return Response(
                {
                    "code": "1001",
                    "error": {"message": _("Invalid fallback reason")},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_agent = str(request.META.get("HTTP_USER_AGENT", "") or "")[:200]
        logger.warning(
            "[TURNSTILE_FALLBACK] reason=%s host=%s ip=%s ua=%s",
            reason,
            request.get_host(),
            get_client_ip(request) or "-",
            user_agent,
        )
        return Response({"code": "0000"}, status=status.HTTP_200_OK)


class CaptchaResponseSerializer:
    """Schema for captcha response."""

    pass


class CaptchaGenerateView(AnonymousPublicViewMixin, APIView):
    """
    Generate a new captcha image.
    GET /api/v1/auth/captcha
    """

    @extend_schema(
        tags=["auth"],
        summary="Generate captcha",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        activate_request_language(request)
        captcha_id = generate_captcha_id()
        captcha_text = generate_captcha_text(length=4)
        save_captcha(captcha_id, captcha_text)

        image_data = generate_svg_captcha(captcha_text)
        expires_at = int(time.time()) + CAPTCHA_EXPIRE_SECONDS

        return Response(
            {
                "code": "0000",
                "data": {
                    "id": captcha_id,
                    "image": image_data,
                    "expires_at": expires_at,
                },
            },
            status=status.HTTP_200_OK,
        )


class CaptchaValidateSerializer:
    """Schema for captcha validation request."""

    pass


class CaptchaValidateView(AnonymousPublicViewMixin, APIView):
    """
    Validate a captcha code.
    POST /api/v1/auth/captcha/validate
    """

    @extend_schema(
        tags=["auth"],
        summary="Validate captcha",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Captcha ID"},
                    "code": {"type": "string", "description": "User entered code"},
                },
                "required": ["id", "code"],
            }
        },
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        activate_request_language(request)
        captcha_id = request.data.get("id")
        user_code = request.data.get("code")

        if not captcha_id or not user_code:
            return Response(
                {
                    "code": "1001",
                    "error": {"message": _("Missing captcha id or code")},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_valid = validate_captcha(captcha_id, user_code)

        if is_valid:
            return Response(
                {"code": "0000", "data": {"valid": True}},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "code": "1001",
                    "error": {"message": _("Invalid or expired captcha")},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
