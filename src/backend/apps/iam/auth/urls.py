from django.urls import path
from rest_framework.permissions import AllowAny

from dj_rest_auth.views import LoginView

from apps.iam.auth.views import (
    CaptchaConfigView,
    CaptchaFallbackReportView,
    CaptchaGenerateView,
    CaptchaValidateView,
    ChangePasswordView,
    CustomUserDetailsView,
    EmailLoginView,
    EmailRegisterView,
    EmailRegisterConfirmView,
    EmailRegisterSendCodeView,
    ForgotPasswordView,
    ForgotPasswordConfirmView,
    GetAvailableScenesView,
    GoogleOAuthConfigView,
    OrgSelectView,
    TokenRefreshView,
    LogoutView,
)


class CustomLoginView(LoginView):
    permission_classes = [AllowAny]


urlpatterns = [
    path("api/v1/auth/captcha-config", CaptchaConfigView.as_view(), name="captcha_config"),
    path(
        "api/v1/auth/captcha-fallback-report",
        CaptchaFallbackReportView.as_view(),
        name="captcha_fallback_report",
    ),
    path("api/v1/auth/captcha", CaptchaGenerateView.as_view(), name="captcha_generate"),
    path("api/v1/auth/captcha/validate", CaptchaValidateView.as_view(), name="captcha_validate"),
    path("api/v1/auth/google/config", GoogleOAuthConfigView.as_view(), name="google_oauth_config"),
    path("api/v1/auth/email-login", EmailLoginView.as_view(), name="email_login"),
    path("api/v1/auth/org-select", OrgSelectView.as_view(), name="org_select"),
    path("api/v1/auth/email-register/send-code", EmailRegisterSendCodeView.as_view(), name="email_register_send_code"),
    path("api/v1/auth/email-register", EmailRegisterView.as_view(), name="email_register"),
    path("api/v1/auth/email-register/confirm", EmailRegisterConfirmView.as_view(), name="email_register_confirm"),
    path("api/v1/auth/forgot-password", ForgotPasswordView.as_view(), name="forgot_password"),
    path("api/v1/auth/forgot-password/confirm", ForgotPasswordConfirmView.as_view(), name="forgot_password_confirm"),
    path("api/v1/auth/change-password", ChangePasswordView.as_view(), name="change_password"),
    path("api/v1/auth/login", CustomLoginView.as_view(), name="rest_login"),
    path("api/v1/auth/logout", LogoutView.as_view(), name="rest_logout"),
    path(
        "api/v1/auth/token/refresh",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "api/v1/auth/user",
        CustomUserDetailsView.as_view(),
        name="rest_user_details",
    ),
    path(
        "api/v1/auth/scenes",
        GetAvailableScenesView.as_view(),
        name="available_scenes",
    ),
]
