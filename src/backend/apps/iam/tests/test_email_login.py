from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.profile_models import Profile


class EmailLoginApiTests(APITestCase):
    def _payload(self, email: str, password: str = "WrongPass123") -> dict:
        return {
            "email": email,
            "password": password,
        }

    def test_pending_registration_user_returns_not_registered(self):
        email = "pending-login@example.com"
        user = User.objects.create_user(
            username="pending-login",
            email=email,
            password="unused",
            is_active=False,
        )
        Profile.objects.create(user=user, registration_completed=False)

        response = self.client.post(
            reverse("email_login"),
            self._payload(email),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "1001")
        self.assertEqual(response.data["error"]["error_code"], "EMAIL_NOT_REGISTERED")
        self.assertIn("email", response.data["error"]["fields"])

    def test_active_user_with_wrong_password_returns_password_error(self):
        email = "active-login@example.com"
        User.objects.create_user(
            username="active-login",
            email=email,
            password="CorrectPass123",
            is_active=True,
        )

        response = self.client.post(
            reverse("email_login"),
            self._payload(email),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "1001")
        self.assertEqual(response.data["error"]["error_code"], "INVALID_PASSWORD")
        self.assertIn("password", response.data["error"]["fields"])

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="site-key",
        TURNSTILE_SECRET_KEY="",
    )
    def test_incomplete_turnstile_configuration_fails_closed(self):
        response = self.client.post(
            reverse("email_login"),
            {
                "email": "anyone@example.com",
                "password": "Pass1234",
                "turnstile_token": "token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.data["error"]["error_code"],
            "TURNSTILE_MISCONFIGURED",
        )
