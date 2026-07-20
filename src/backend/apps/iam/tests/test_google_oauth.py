"""Tests for Google OAuth login and social registration."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.models import Membership, Organization
from apps.iam.services.registration_service import complete_social_user_registration


@override_settings(
    GOOGLE_CLIENT_ID="test-client-id",
    GOOGLE_CLIENT_SECRET="test-client-secret",
    HFL_GOOGLE_OAUTH_ENABLED=True,
    FRONTEND_URL="https://app.example.com",
)
@patch.dict("os.environ", {"HFL_GOOGLE_OAUTH_ENABLED": "true"})
class GoogleOAuthConfigTests(APITestCase):
    def test_google_config_enabled(self):
        response = self.client.get(reverse("google_oauth_config"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "0000")
        self.assertTrue(response.data["data"]["enabled"])
        self.assertEqual(
            response.data["data"]["login_url"],
            "https://app.example.com/accounts/google/login/",
        )

    @override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    @patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""})
    def test_google_config_requires_credentials(self):
        response = self.client.get(reverse("google_oauth_config"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["data"]["enabled"])


@override_settings(
    GOOGLE_CLIENT_ID="test-client-id",
    GOOGLE_CLIENT_SECRET="test-client-secret",
    HFL_GOOGLE_OAUTH_ENABLED=False,
    FRONTEND_URL="https://app.example.com",
)
@patch.dict("os.environ", {"HFL_GOOGLE_OAUTH_ENABLED": "false"})
class GoogleOAuthDisabledTests(APITestCase):
    def test_google_config_disabled(self):
        response = self.client.get(reverse("google_oauth_config"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["data"]["enabled"])

    def test_google_login_endpoint_is_forbidden(self):
        response = self.client.get(reverse("google_login"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SocialRegistrationServiceTests(APITestCase):
    def test_complete_social_user_registration_provisions_org(self):
        user = User.objects.create_user(
            username="google-user",
            email="google-user@example.com",
            password="unused",
            is_active=False,
        )

        org = complete_social_user_registration(user)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(Organization.objects.filter(pk=org.pk).exists())
        membership = Membership.objects.get(user=user, organization=org)
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(Membership.objects.filter(user=user).count(), 1)


@override_settings(
    GOOGLE_CLIENT_ID="test-client-id",
    GOOGLE_CLIENT_SECRET="test-client-secret",
    HFL_GOOGLE_OAUTH_ENABLED=True,
    FRONTEND_URL="https://app.example.com",
)
@patch.dict("os.environ", {"HFL_GOOGLE_OAUTH_ENABLED": "true"})
class GoogleOAuthCallbackTests(APITestCase):
    def test_oauth_callback_issues_cookies_and_redirects(self):
        user = User.objects.create_user(
            username="oauth-callback",
            email="oauth-callback@example.com",
            password="Pass1234",
            is_active=True,
        )
        org = Organization.objects.create(key="oauth-org", name="OAuth Org", is_active=True)
        Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER, is_active=True)

        client = Client()
        client.force_login(user)
        response = client.get(reverse("oauth_callback"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("https://app.example.com/auth/oauth/callback", response["Location"])
        self.assertIn("org_key=oauth-org", response["Location"])
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
