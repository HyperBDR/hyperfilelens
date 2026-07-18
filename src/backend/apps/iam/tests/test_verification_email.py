from django.core import mail
from django.test import TestCase, override_settings

from apps.iam.services.verification_email import (
    VerificationEmailKind,
    send_verification_code_email,
)


@override_settings(DEFAULT_FROM_EMAIL="HyperFileLens <noreply@test.local>")
class VerificationEmailTests(TestCase):
    def test_registration_email_subject_starts_with_code(self):
        send_verification_code_email(
            recipient="user@example.com",
            code="617005",
            minutes=15,
            kind=VerificationEmailKind.REGISTRATION,
        )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "617005 is your HyperFileLens verification code")
        self.assertIn("617005", message.body)
        self.assertIn("617005\n", message.body)
        self.assertNotIn("Hello 2776998293", message.body)
        self.assertEqual(len(message.alternatives), 1)
        html, mime = message.alternatives[0]
        self.assertEqual(mime, "text/html")
        self.assertIn("617005", html)
        self.assertIn("HyperFileLens", html)
        self.assertIn("letter-spacing: 5px", html)

    def test_password_reset_email_subject_starts_with_code(self):
        send_verification_code_email(
            recipient="user@example.com",
            code="123456",
            minutes=10,
            kind=VerificationEmailKind.PASSWORD_RESET,
        )

        message = mail.outbox[0]
        self.assertEqual(message.subject, "123456 is your HyperFileLens password reset code")
        self.assertIn("password reset", message.body.lower())
