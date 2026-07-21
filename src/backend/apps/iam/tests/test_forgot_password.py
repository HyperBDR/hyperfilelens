from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.profile_models import Profile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ForgotPasswordApiTests(APITestCase):
    def _payload(self, email: str) -> dict:
        return {"email": email}

    def test_active_user_receives_reset_email(self):
        email = "active-reset@example.com"
        User.objects.create_user(
            username="active-reset",
            email=email,
            password="Pass1234",
            is_active=True,
        )

        response = self.client.post(
            reverse("forgot_password"),
            self._payload(email),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "0000")
        self.assertFalse(response.data["data"].get("pending_registration"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password reset", mail.outbox[0].subject.lower())

    def test_pending_registration_user_receives_registration_email(self):
        email = "pending-reset@example.com"
        user = User.objects.create_user(
            username="pending-reset",
            email=email,
            password="unused",
            is_active=False,
        )
        Profile.objects.create(user=user, registration_completed=False)

        response = self.client.post(
            reverse("forgot_password"),
            self._payload(email),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "0000")
        self.assertTrue(response.data["data"]["pending_registration"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verification code", mail.outbox[0].subject.lower())

    def test_unknown_email_returns_not_registered_error(self):
        response = self.client.post(
            reverse("forgot_password"),
            self._payload("missing@example.com"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "1001")
        self.assertEqual(response.data["error"]["error_code"], "EMAIL_NOT_REGISTERED")
        self.assertIn("email", response.data["error"]["fields"])
        self.assertEqual(len(mail.outbox), 0)
