"""License API tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.subscription.models import License
from apps.subscription.services.internal.crypto import generate_activation_code
from apps.subscription.services.interface import get_or_create_machine_code


class LicenseApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="license-api@test.local",
            email="license-api@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="license-test-org", name="License Test Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.client.force_authenticate(user=self.user)

    def _headers(self):
        return {"HTTP_X_ORG_KEY": self.org.key}

    def test_current_without_license(self):
        resp = self.client.get(
            "/api/v1/subscription/licenses/current/",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_valid"])
        self.assertIn("machine_code", resp.data)
        self.assertIn("limits", resp.data)
        self.assertIn("usage", resp.data)
        self.assertEqual(resp.data["limits"]["max_users"], 50)
        self.assertFalse(resp.data.get("enforcement_enabled", True))

    @override_settings(DEBUG=True)
    def test_activate_dev_license(self):
        resp = self.client.post(
            "/api/v1/subscription/licenses/activate/",
            {"activation_code": "DEV-UNLIMITED"},
            format="json",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertTrue(License.objects.filter(organization=self.org).exists())

    def test_activate_with_signed_code(self):
        machine_code = get_or_create_machine_code(organization=self.org, user=self.user)
        code = generate_activation_code(
            license_key="TEST-KEY-001",
            machine_code=machine_code,
            limits={
                "max_users": 100,
                "max_nodes": 10,
                "max_storage_gb": 200,
            },
        )
        resp = self.client.post(
            "/api/v1/subscription/licenses/activate/",
            {"activation_code": code},
            format="json",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        lic = License.objects.get(organization=self.org)
        self.assertEqual(lic.max_users, 100)

    def test_validate_always_allows_in_dev(self):
        resp = self.client.get(
            "/api/v1/subscription/licenses/validate/",
            {"quota_type": "users", "amount": "9999"},
            **self._headers(),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_valid"])

    def test_history_empty(self):
        resp = self.client.get(
            "/api/v1/subscription/licenses/history/",
            **self._headers(),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)
