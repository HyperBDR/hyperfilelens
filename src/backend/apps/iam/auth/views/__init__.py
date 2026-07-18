"""
Views for user authentication and management.
"""

from .captcha import (
    CaptchaConfigView,
    CaptchaFallbackReportView,
    CaptchaGenerateView,
    CaptchaValidateView,
)
from .login import EmailLoginView, TokenRefreshView, LogoutView, OrgSelectView
from .oauth import GoogleOAuthCallbackView, GoogleOAuthConfigView
from .registration import (
    ChangePasswordView,
    EmailRegisterView,
    EmailRegisterConfirmView,
    EmailRegisterSendCodeView,
    ForgotPasswordView,
    ForgotPasswordConfirmView,
)
from .scenes import GetAvailableScenesView
from .user import CustomUserDetailsView

__all__ = [
    "CaptchaConfigView",
    "CaptchaFallbackReportView",
    "CaptchaGenerateView",
    "CaptchaValidateView",
    "ChangePasswordView",
    "CustomUserDetailsView",
    "EmailLoginView",
    "EmailRegisterView",
    "EmailRegisterConfirmView",
    "EmailRegisterSendCodeView",
    "ForgotPasswordView",
    "ForgotPasswordConfirmView",
    "GetAvailableScenesView",
    "GoogleOAuthCallbackView",
    "GoogleOAuthConfigView",
    "OrgSelectView",
    "TokenRefreshView",
    "LogoutView",
]
