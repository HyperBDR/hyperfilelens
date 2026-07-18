from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsPermissionsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username="user@test.com",
            email="user@test.com",
            password="Pass1234",
        )

    def test_anonymous_denied(self):
        response = self.client.get("/api/v1/platform-ops/users")
        self.assertIn(response.status_code, (401, 403))

    def test_non_staff_denied(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/platform-ops/users")
        self.assertEqual(response.status_code, 403)

    def test_staff_denied_on_tenant_listener(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get("/api/v1/platform-ops/users")
        self.assertEqual(response.status_code, 403)

    def test_staff_allowed_on_ops_listener(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            "/api/v1/platform-ops/users",
            HTTP_X_HFL_SITE_ROLE="ops",
        )
        self.assertEqual(response.status_code, 200)
