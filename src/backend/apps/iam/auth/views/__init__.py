"""
Views for user authentication and management.
"""

from .turnstile import TurnstileConfigView
from .login import EmailLoginView, TokenRefreshView, LogoutView, OrgSelectView
from .oauth import (
    GoogleOAuthCallbackView,
    GoogleOAuthConfigView,
    GoogleOAuthErrorEventConsumeView,
)
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
    "GoogleOAuthErrorEventConsumeView",
    "OrgSelectView",
    "TokenRefreshView",
    "TurnstileConfigView",
    "LogoutView",
]
