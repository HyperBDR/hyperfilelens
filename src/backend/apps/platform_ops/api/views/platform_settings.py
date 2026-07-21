"""Platform Ops structured platform settings APIs."""

from __future__ import annotations

from django.core.mail import EmailMessage, get_connection
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.configuration.models import GlobalConfig
from apps.configuration.selectors.interface import get_config, invalidate_config_cache
from apps.configuration.services.internal.registry import registry_by_key
from apps.configuration.services.internal.validation import validate_config_key
from apps.iam import conf as iam_conf
from apps.iam.config import (
    get_password_reset_timeout_seconds,
    get_password_reset_verification_code_minutes,
    get_registration_token_expiry_hours,
    get_registration_verification_code_minutes,
)
from apps.iam.models import Organization
from apps.insight import conf as insight_conf
from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.services.internal.audit import write_platform_audit_log
from apps.platform_ops.services.internal.runtime_settings import (
    KEY_AI_AZURE_BASE,
    KEY_AI_LANGFUSE_BASE,
    KEY_AI_LANGFUSE_ENABLED,
    KEY_AI_OPENAI_BASE,
    KEY_EMAIL_BACKEND,
    KEY_EMAIL_FROM,
    KEY_EMAIL_HOST,
    KEY_EMAIL_HOST_USER,
    KEY_EMAIL_PORT,
    KEY_EMAIL_USE_SSL,
    KEY_EMAIL_USE_TLS,
    KEY_IDENTITY_EMAIL_SIGNUP,
    KEY_IDENTITY_GOOGLE_CLIENT_ID,
    KEY_IDENTITY_GOOGLE_OAUTH,
    KEY_IDENTITY_OPS_CIDRS,
    KEY_IDENTITY_PASSWORD_RESET,
    KEY_IDENTITY_PLATFORM_OPS,
    KEY_IDENTITY_TURNSTILE_SITE,
    SECRET_KEY_AZURE,
    SECRET_KEY_EMAIL_PASSWORD,
    SECRET_KEY_GEMINI,
    SECRET_KEY_GOOGLE,
    SECRET_KEY_LANGFUSE_PUBLIC,
    SECRET_KEY_LANGFUSE_SECRET,
    SECRET_KEY_OPENAI,
    SECRET_KEY_TURNSTILE,
    email_signup_enabled,
    email_connection_kwargs,
    gemini_api_key,
    get_source,
    google_client_id,
    google_oauth_enabled,
    mask_secret,
    openai_api_base,
    openai_api_key,
    platform_ops_allowed_cidrs,
    platform_ops_enabled,
    secret_configured,
    self_service_password_reset_enabled,
    set_bool,
    set_str_list,
    set_value,
    sync_google_social_app,
    turnstile_site_key,
    turnstile_enabled,
)
from apps.platform_ops.services.internal.runtime_settings import (
    azure_openai_api_base as runtime_azure_base,
)
from apps.platform_ops.services.internal.runtime_settings import (
    azure_openai_api_key as runtime_azure_key,
)
from apps.platform_ops.services.internal.runtime_settings import (
    langfuse_base_url,
    langfuse_enabled,
    langfuse_public_key,
    langfuse_secret_key,
)
from apps.configuration.tenant_conf import CONFIG_KEY_DR_TASK_CONCURRENCY, DEFAULT_DR_TASK_CONCURRENCY
from apps.storage import conf as storage_conf
from apps.subscription.services.interface import activate_license, get_or_create_machine_code
from common.deploy.site import tenant_public_url


def _audit(request, action: str, details: dict | None = None) -> None:
    write_platform_audit_log(
        request=request,
        action=action,
        target_type="platform_settings",
        target_id=action,
        details=details or {},
    )


def _google_redirect_uri() -> str:
    return f"{tenant_public_url()}/accounts/google/login/callback/"


class PlatformOpsSettingsEmailView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        cfg = email_connection_kwargs()
        return Response(
            {
                "backend": cfg["backend"],
                "host": cfg["host"],
                "port": cfg["port"],
                "use_tls": cfg["use_tls"],
                "use_ssl": cfg["use_ssl"],
                "host_user": cfg["username"],
                "password_configured": secret_configured(
                    SECRET_KEY_EMAIL_PASSWORD,
                    env_name="EMAIL_HOST_PASSWORD",
                    settings_attr="EMAIL_HOST_PASSWORD",
                ),
                "password_hint": mask_secret(cfg["password"]) if cfg["password"] else "",
                "from_email": cfg["from_email"],
                "sources": {
                    "host": get_source(KEY_EMAIL_HOST),
                    "from_email": get_source(KEY_EMAIL_FROM),
                },
            }
        )

    def patch(self, request):
        data = request.data or {}
        mapping = {
            "backend": KEY_EMAIL_BACKEND,
            "host": KEY_EMAIL_HOST,
            "host_user": KEY_EMAIL_HOST_USER,
            "from_email": KEY_EMAIL_FROM,
        }
        for field, key in mapping.items():
            if field in data:
                set_value(key=key, value=str(data[field] or ""), user=request.user)
        if "port" in data:
            set_value(key=KEY_EMAIL_PORT, value=str(int(data["port"])), user=request.user)
        if "use_tls" in data:
            set_bool(KEY_EMAIL_USE_TLS, bool(data["use_tls"]), user=request.user)
        if "use_ssl" in data:
            set_bool(KEY_EMAIL_USE_SSL, bool(data["use_ssl"]), user=request.user)
        if "password" in data and str(data["password"] or "").strip():
            set_value(key=SECRET_KEY_EMAIL_PASSWORD, secret=str(data["password"]), user=request.user)
        _audit(request, "platform_settings.email.update")
        return self.get(request)


class PlatformOpsSettingsEmailTestView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        recipient = str((request.data or {}).get("recipient") or request.user.email or "").strip()
        if not recipient:
            return Response({"detail": "recipient is required"}, status=status.HTTP_400_BAD_REQUEST)
        cfg = email_connection_kwargs()
        try:
            connection = get_connection(
                backend=cfg["backend"],
                host=cfg["host"] or None,
                port=cfg["port"] or None,
                username=cfg["username"] or None,
                password=cfg["password"] or None,
                use_tls=cfg["use_tls"],
                use_ssl=cfg["use_ssl"],
            )
            EmailMessage(
                subject="HyperFileLens test email",
                body="This is a test email from Admin Console platform settings.",
                from_email=cfg["from_email"],
                to=[recipient],
                connection=connection,
            ).send()
        except Exception as exc:
            return Response({"ok": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _audit(request, "platform_settings.email.test", {"recipient": recipient})
        return Response({"ok": True, "recipient": recipient})


class PlatformOpsSettingsIdentityView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        return Response(
            {
                "email_signup_enabled": email_signup_enabled(),
                "self_service_password_reset": self_service_password_reset_enabled(),
                "platform_ops_enabled": platform_ops_enabled(),
                "platform_ops_allowed_cidrs": platform_ops_allowed_cidrs(),
                "turnstile_enabled": turnstile_enabled(),
                "turnstile_site_key": turnstile_site_key(),
                "turnstile_secret_configured": secret_configured(
                    SECRET_KEY_TURNSTILE,
                    env_name="TURNSTILE_SECRET_KEY",
                    settings_attr="TURNSTILE_SECRET_KEY",
                ),
                "google_client_id": google_client_id(),
                "google_client_secret_configured": secret_configured(
                    SECRET_KEY_GOOGLE,
                    env_name="GOOGLE_CLIENT_SECRET",
                    settings_attr="GOOGLE_CLIENT_SECRET",
                ),
                "google_oauth_enabled": google_oauth_enabled(),
                "google_oauth_redirect_uri": _google_redirect_uri(),
                "iam": {
                    "registration_verification_code_minutes": get_registration_verification_code_minutes(),
                    "registration_token_expiry_hours": get_registration_token_expiry_hours(),
                    "password_reset_verification_code_minutes": get_password_reset_verification_code_minutes(),
                    "password_reset_timeout_seconds": get_password_reset_timeout_seconds(),
                },
            }
        )

    def patch(self, request):
        data = request.data or {}
        bool_map = {
            "email_signup_enabled": KEY_IDENTITY_EMAIL_SIGNUP,
            "google_oauth_enabled": KEY_IDENTITY_GOOGLE_OAUTH,
            "self_service_password_reset": KEY_IDENTITY_PASSWORD_RESET,
            "platform_ops_enabled": KEY_IDENTITY_PLATFORM_OPS,
        }
        for field, key in bool_map.items():
            if field in data:
                set_bool(key, bool(data[field]), user=request.user)
        if "platform_ops_allowed_cidrs" in data:
            cidrs = data["platform_ops_allowed_cidrs"]
            if isinstance(cidrs, str):
                cidrs = [part.strip() for part in cidrs.split(",") if part.strip()]
            set_str_list(KEY_IDENTITY_OPS_CIDRS, list(cidrs or []), user=request.user)
        if "turnstile_site_key" in data:
            set_value(key=KEY_IDENTITY_TURNSTILE_SITE, value=str(data["turnstile_site_key"] or ""), user=request.user)
        if "turnstile_secret_key" in data and str(data["turnstile_secret_key"] or "").strip():
            set_value(key=SECRET_KEY_TURNSTILE, secret=str(data["turnstile_secret_key"]), user=request.user)
        if "google_client_id" in data:
            set_value(key=KEY_IDENTITY_GOOGLE_CLIENT_ID, value=str(data["google_client_id"] or ""), user=request.user)
        if "google_client_secret" in data and str(data["google_client_secret"] or "").strip():
            set_value(key=SECRET_KEY_GOOGLE, secret=str(data["google_client_secret"]), user=request.user)

        iam = data.get("iam") or {}
        if isinstance(iam, dict):
            self._patch_iam_global(iam, user=request.user)

        sync_google_social_app()
        _audit(request, "platform_settings.identity.update")
        return self.get(request)

    def _patch_iam_global(self, iam: dict, *, user) -> None:
        specs = {
            "registration_verification_code_minutes": (
                iam_conf.CONFIG_KEY_REGISTRATION_CODE_MINUTES,
                GlobalConfig.ValueType.NUMBER,
                iam_conf.DEFAULT_REGISTRATION_VERIFICATION_CODE_MINUTES,
            ),
            "registration_token_expiry_hours": (
                iam_conf.CONFIG_KEY_REGISTRATION_TOKEN_EXPIRY_HOURS,
                GlobalConfig.ValueType.NUMBER,
                iam_conf.DEFAULT_REGISTRATION_TOKEN_EXPIRY_HOURS,
            ),
            "password_reset_verification_code_minutes": (
                iam_conf.CONFIG_KEY_PASSWORD_RESET_CODE_MINUTES,
                GlobalConfig.ValueType.NUMBER,
                iam_conf.DEFAULT_PASSWORD_RESET_VERIFICATION_CODE_MINUTES,
            ),
            "password_reset_timeout_seconds": (
                iam_conf.CONFIG_KEY_PASSWORD_RESET_TIMEOUT,
                GlobalConfig.ValueType.NUMBER,
                iam_conf.DEFAULT_PASSWORD_RESET_TIMEOUT_SECONDS,
            ),
        }
        for field, (key, value_type, default) in specs.items():
            if field not in iam:
                continue
            value = iam[field]
            validate_config_key(key)
            registry = registry_by_key().get(key)
            GlobalConfig.objects.update_or_create(
                key=key,
                scope=GlobalConfig.Scope.GLOBAL,
                tenant_key="",
                defaults={
                    "value": value,
                    "value_type": value_type,
                    "category": registry.category if registry else "iam",
                    "description": registry.description if registry else "",
                    "is_active": True,
                    "updated_by": user,
                    "created_by": user,
                },
            )
            invalidate_config_cache(key=key, tenant_key="", scope="global")


class PlatformOpsSettingsAiView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        return Response(
            {
                "openai_api_key_configured": bool(openai_api_key()),
                "openai_api_key_hint": mask_secret(openai_api_key() or ""),
                "openai_api_base": openai_api_base(),
                "azure_openai_api_key_configured": bool(runtime_azure_key()),
                "azure_openai_api_key_hint": mask_secret(runtime_azure_key() or ""),
                "azure_openai_api_base": runtime_azure_base() or "",
                "gemini_api_key_configured": bool(gemini_api_key()),
                "gemini_api_key_hint": mask_secret(gemini_api_key() or ""),
                "langfuse_enabled": langfuse_enabled(),
                "langfuse_public_key_configured": bool(langfuse_public_key()),
                "langfuse_secret_key_configured": bool(langfuse_secret_key()),
                "langfuse_base_url": langfuse_base_url(),
                "llm": {
                    "provider": get_config(
                        insight_conf.CONFIG_KEY_LLM_PROVIDER,
                        default=insight_conf.DEFAULT_LLM_PROVIDER,
                    ),
                    "output_language": get_config(
                        insight_conf.CONFIG_KEY_LLM_OUTPUT_LANGUAGE,
                        default=insight_conf.DEFAULT_LLM_OUTPUT_LANGUAGE,
                    ),
                    "openai_model": get_config(
                        insight_conf.CONFIG_KEY_OPENAI_MODEL,
                        default=insight_conf.DEFAULT_OPENAI_MODEL,
                    ),
                },
            }
        )

    def patch(self, request):
        data = request.data or {}
        secret_fields = {
            "openai_api_key": SECRET_KEY_OPENAI,
            "azure_openai_api_key": SECRET_KEY_AZURE,
            "gemini_api_key": SECRET_KEY_GEMINI,
            "langfuse_public_key": SECRET_KEY_LANGFUSE_PUBLIC,
            "langfuse_secret_key": SECRET_KEY_LANGFUSE_SECRET,
        }
        for field, key in secret_fields.items():
            if field in data and str(data[field] or "").strip():
                set_value(key=key, secret=str(data[field]), user=request.user)
        if "openai_api_base" in data:
            set_value(key=KEY_AI_OPENAI_BASE, value=str(data["openai_api_base"] or ""), user=request.user)
        if "azure_openai_api_base" in data:
            set_value(key=KEY_AI_AZURE_BASE, value=str(data["azure_openai_api_base"] or ""), user=request.user)
        if "langfuse_base_url" in data:
            set_value(key=KEY_AI_LANGFUSE_BASE, value=str(data["langfuse_base_url"] or ""), user=request.user)
        if "langfuse_enabled" in data:
            set_bool(KEY_AI_LANGFUSE_ENABLED, bool(data["langfuse_enabled"]), user=request.user)

        llm = data.get("llm") or {}
        if isinstance(llm, dict):
            self._patch_llm_global(llm, user=request.user)

        _audit(request, "platform_settings.ai.update")
        return self.get(request)

    def _patch_llm_global(self, llm: dict, *, user) -> None:
        mapping = {
            "provider": (insight_conf.CONFIG_KEY_LLM_PROVIDER, GlobalConfig.ValueType.STRING),
            "output_language": (insight_conf.CONFIG_KEY_LLM_OUTPUT_LANGUAGE, GlobalConfig.ValueType.STRING),
            "openai_model": (insight_conf.CONFIG_KEY_OPENAI_MODEL, GlobalConfig.ValueType.STRING),
        }
        for field, (key, value_type) in mapping.items():
            if field not in llm:
                continue
            registry = registry_by_key().get(key)
            GlobalConfig.objects.update_or_create(
                key=key,
                scope=GlobalConfig.Scope.GLOBAL,
                tenant_key="",
                defaults={
                    "value": llm[field],
                    "value_type": value_type,
                    "category": registry.category if registry else "insight",
                    "description": registry.description if registry else "",
                    "is_active": True,
                    "updated_by": user,
                    "created_by": user,
                },
            )
            invalidate_config_cache(key=key, tenant_key="", scope="global")


class PlatformOpsSettingsAiTestView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        key = openai_api_key() or runtime_azure_key() or gemini_api_key()
        if not key:
            return Response({"ok": False, "error": "No API key configured"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True, "message": "API key is configured"})


class PlatformOpsSettingsDefaultsView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        retention_default = get_config(storage_conf.CONFIG_KEY_RETENTION, default={})
        filters_default = get_config(storage_conf.CONFIG_KEY_FILTERS, default={})
        dr_default = get_config(
            CONFIG_KEY_DR_TASK_CONCURRENCY,
            default=DEFAULT_DR_TASK_CONCURRENCY,
        )
        return Response(
            {
                "dr_task_concurrency": dr_default,
                "retention_default": retention_default,
                "filters_default": filters_default,
            }
        )

    def patch(self, request):
        data = request.data or {}
        if "dr_task_concurrency" in data:
            GlobalConfig.objects.update_or_create(
                key=CONFIG_KEY_DR_TASK_CONCURRENCY,
                scope=GlobalConfig.Scope.GLOBAL,
                tenant_key="",
                defaults={
                    "value": int(data["dr_task_concurrency"]),
                    "value_type": GlobalConfig.ValueType.NUMBER,
                    "category": "file_dr",
                    "is_active": True,
                    "updated_by": request.user,
                    "created_by": request.user,
                },
            )
            invalidate_config_cache(key=CONFIG_KEY_DR_TASK_CONCURRENCY, tenant_key="", scope="global")
        if "retention_default" in data:
            self._upsert_object(storage_conf.CONFIG_KEY_RETENTION, data["retention_default"], user=request.user)
        if "filters_default" in data:
            self._upsert_object(storage_conf.CONFIG_KEY_FILTERS, data["filters_default"], user=request.user)
        _audit(request, "platform_settings.defaults.update")
        return self.get(request)

    def _upsert_object(self, key: str, value, *, user) -> None:
        registry = registry_by_key().get(key)
        GlobalConfig.objects.update_or_create(
            key=key,
            scope=GlobalConfig.Scope.GLOBAL,
            tenant_key="",
            defaults={
                "value": value,
                "value_type": GlobalConfig.ValueType.OBJECT,
                "category": registry.category if registry else "backup",
                "description": registry.description if registry else "",
                "is_active": True,
                "updated_by": user,
                "created_by": user,
            },
        )
        invalidate_config_cache(key=key, tenant_key="", scope="global")


class PlatformOpsSettingsEnvironmentView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        from apps.platform_ops.selectors.internal.system import deploy_profile_staff_payload, system_health_payload

        cfg = email_connection_kwargs()
        return Response(
            {
                "app_version": deploy_profile_staff_payload().get("app_version"),
                "agent_version": deploy_profile_staff_payload().get("agent_version"),
                "django_debug": deploy_profile_staff_payload().get("django_debug"),
                "effective": {
                    "tenant_public_url": tenant_public_url(),
                    "email_signup_enabled": email_signup_enabled(),
                    "self_service_password_reset": self_service_password_reset_enabled(),
                    "platform_ops_enabled": platform_ops_enabled(),
                    "turnstile_enabled": turnstile_enabled(),
                    "google_oauth_enabled": google_oauth_enabled(),
                    "email_host_configured": bool(cfg["host"]),
                    "email_password_configured": bool(cfg["password"]),
                    "openai_configured": bool(openai_api_key()),
                },
                "sources": {
                    "email_signup_enabled": get_source(KEY_IDENTITY_EMAIL_SIGNUP),
                    "google_oauth_enabled": get_source(KEY_IDENTITY_GOOGLE_OAUTH),
                    "turnstile_enabled": "env",
                    "email_host": get_source(KEY_EMAIL_HOST),
                },
                "health": system_health_payload(),
            }
        )


class PlatformOpsBillingLicenseActivateView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        activation_code = str((request.data or {}).get("activation_code") or "").strip()
        if not activation_code:
            return Response({"detail": "activation_code is required"}, status=status.HTTP_400_BAD_REQUEST)
        org = Organization.objects.filter(is_active=True).order_by("id").first()
        if org is None:
            raise Http404
        try:
            lic, _change = activate_license(
                organization=org,
                user=request.user,
                activation_code=activation_code,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _audit(request, "platform_settings.license.activate", {"org_key": org.key})
        machine_code = get_or_create_machine_code(organization=org, user=request.user)
        return Response(
            {
                "ok": True,
                "organization_key": org.key,
                "machine_code": machine_code,
                "license_key": lic.license_key,
                "status": lic.status,
            }
        )
