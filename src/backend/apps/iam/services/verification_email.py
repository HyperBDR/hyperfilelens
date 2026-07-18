"""
Branded verification-code emails (HTML + plain text) for IAM flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone
from django.utils.translation import gettext as _

BRAND_COLOR = "#6d28d9"
TAGLINE = "AI-Powered File Backup Insights."


class VerificationEmailKind(str, Enum):
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"


@dataclass(frozen=True)
class VerificationEmailContent:
    subject: str
    intro_html: str
    intro_plain: str
    ignore_html: str
    ignore_plain: str


def _content_for_kind(kind: VerificationEmailKind, code: str, minutes: int) -> VerificationEmailContent:
    if kind is VerificationEmailKind.REGISTRATION:
        return VerificationEmailContent(
            subject=_("%(code)s is your HyperFileLens verification code") % {"code": code},
            intro_html=_(
                "Thank you for choosing <strong>HyperFileLens</strong>. "
                "Please use the following verification code to complete your registration:"
            ),
            intro_plain=_(
                "Thank you for choosing HyperFileLens. "
                "Please use the following verification code to complete your registration:"
            ),
            ignore_html=_(
                "If you did not create a HyperFileLens account, please ignore this email."
            ),
            ignore_plain=_(
                "If you did not create a HyperFileLens account, please ignore this email."
            ),
        )
    if kind is VerificationEmailKind.PASSWORD_RESET:
        return VerificationEmailContent(
            subject=_("%(code)s is your HyperFileLens password reset code") % {"code": code},
            intro_html=_(
                "We received a request to reset your <strong>HyperFileLens</strong> password. "
                "Use the verification code below to continue:"
            ),
            intro_plain=_(
                "We received a request to reset your HyperFileLens password. "
                "Use the verification code below to continue:"
            ),
            ignore_html=_(
                "If you did not request a password reset, please ignore this email."
            ),
            ignore_plain=_(
                "If you did not request a password reset, please ignore this email."
            ),
        )
    raise ValueError(f"Unknown verification email kind: {kind}")


def _build_plain_body(content: VerificationEmailContent, code: str, minutes: int) -> str:
    expiry = _("This code will expire in %(minutes)s minutes.") % {"minutes": minutes}
    year = timezone.now().year
    footer = _("© %(year)s HyperFileLens. %(tagline)s") % {"year": year, "tagline": TAGLINE}
    return "\n".join(
        [
            "HyperFileLens",
            "",
            _("Hello,"),
            "",
            content.intro_plain,
            "",
            code,
            "",
            expiry,
            "",
            content.ignore_plain,
            "",
            footer,
        ]
    )


def _build_html_body(content: VerificationEmailContent, code: str, minutes: int) -> str:
    expiry = _("This code will expire in <strong>%(minutes)s minutes</strong>.") % {
        "minutes": minutes
    }
    year = timezone.now().year
    footer = _("© %(year)s HyperFileLens. %(tagline)s") % {"year": year, "tagline": TAGLINE}
    return f"""\
<div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; color: #333;">
  <h2 style="color: {BRAND_COLOR}; margin: 0 0 16px;">HyperFileLens</h2>
  <p style="margin: 0 0 16px;">{_('Hello,')}</p>
  <p style="margin: 0 0 16px; line-height: 1.5;">{content.intro_html}</p>
  <div style="background: #f3f4f6; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: {BRAND_COLOR}; margin: 20px 0; border-radius: 8px;">
    {code}
  </div>
  <p style="font-size: 14px; color: #666; line-height: 1.6; margin: 0 0 16px;">
    {expiry}<br>
    {content.ignore_html}
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0 16px;">
  <p style="font-size: 12px; color: #999; text-align: center; margin: 0;">
    {footer}
  </p>
</div>"""


def send_verification_code_email(
    *,
    recipient: str,
    code: str,
    minutes: int,
    kind: VerificationEmailKind,
) -> None:
    """Send a branded verification email with HTML and plain-text alternatives."""
    content = _content_for_kind(kind, code, minutes)
    plain_body = _build_plain_body(content, code, minutes)
    html_body = _build_html_body(content, code, minutes)
    from apps.platform_ops.services.internal.runtime_settings import email_connection_kwargs

    cfg = email_connection_kwargs()
    connection = get_connection(
        backend=cfg["backend"],
        host=cfg["host"] or None,
        port=cfg["port"] or None,
        username=cfg["username"] or None,
        password=cfg["password"] or None,
        use_tls=cfg["use_tls"],
        use_ssl=cfg["use_ssl"],
    )

    message = EmailMultiAlternatives(
        subject=content.subject,
        body=plain_body,
        from_email=cfg["from_email"],
        to=[recipient],
        connection=connection,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
