from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(
    HFL_EMAIL_SIGNUP_ENABLED=False,
    HFL_PLATFORM_OPS_ENABLED=True,
    HFL_ADMIN_PORT=11444,
    FRONTEND_URL="https://127.0.0.1:11443",
    EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    EMAIL_HOST="",
    EMAIL_HOST_USER="",
    EMAIL_HOST_PASSWORD="",
)
@patch.dict("os.environ", {"HFL_EMAIL_SIGNUP_ENABLED": "false"})
class DeployProfileViewTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )

    def test_anonymous_profile(self):
        response = self.client.get(
            "/api/v1/meta/deploy-profile",
            HTTP_HOST="127.0.0.1:11443",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["site_role"], "tenant")
        self.assertEqual(
            response.data["admin_console_url"],
            "https://127.0.0.1:11444",
        )
        self.assertFalse(response.data["admin_console_entry_visible"])
        self.assertFalse(response.data["platform_ops_access_allowed"])
        self.assertFalse(response.data["email_signup_enabled"])
        self.assertFalse(response.data["password_reset_available"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_is_available_with_deliverable_test_backend(self):
        response = self.client.get("/api/v1/meta/deploy-profile")
        self.assertTrue(response.data["password_reset_available"])

    def test_ops_listener_hides_tenant_registration(self):
        response = self.client.get(
            "/api/v1/meta/deploy-profile",
            HTTP_X_HFL_SITE_ROLE="ops",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["email_signup_enabled"])

    def test_staff_is_denied_platform_ops_on_tenant_listener(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get("/api/v1/meta/deploy-profile")
        self.assertTrue(response.data["admin_console_entry_visible"])
        self.assertFalse(response.data["platform_ops_access_allowed"])
        self.assertTrue(response.data["is_staff"])

    def test_staff_is_allowed_platform_ops_on_ops_listener(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            "/api/v1/meta/deploy-profile",
            HTTP_X_HFL_SITE_ROLE="ops",
        )
        self.assertEqual(response.data["site_role"], "ops")
        self.assertFalse(response.data["admin_console_entry_visible"])
        self.assertTrue(response.data["platform_ops_access_allowed"])
        self.assertEqual(response.data["landing_path"], "/platform-ops/overview")

    @override_settings(FRONTEND_URL="https://app.example.com:11443", HFL_ADMIN_PORT=11444)
    def test_admin_console_url_uses_tenant_host_and_configured_port(self):
        response = self.client.get(
            "/api/v1/meta/deploy-profile",
            HTTP_HOST="app.example.com:11443",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(
            response.data["admin_console_url"],
            "https://app.example.com:11444",
        )

    @override_settings(
        FRONTEND_URL="https://app.example.com",
        HFL_ADMIN_PORT=11444,
        HFL_ADMIN_PUBLIC_URL="https://ops.example.com/",
    )
    def test_admin_console_url_prefers_configured_public_url(self):
        response = self.client.get(
            "/api/v1/meta/deploy-profile",
            HTTP_HOST="app.example.com",
            HTTP_X_FORWARDED_PROTO="https",
        )
        self.assertEqual(
            response.data["admin_console_url"],
            "https://ops.example.com",
        )

    def test_invalid_access_token_cookie_is_treated_as_anonymous(self):
        self.client.cookies["access_token"] = "not-a-valid-jwt"
        response = self.client.get("/api/v1/meta/deploy-profile")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["platform_ops_access_allowed"])
        self.assertFalse(response.data["is_staff"])
