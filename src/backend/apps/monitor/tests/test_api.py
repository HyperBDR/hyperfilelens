"""System monitor API tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization


class SystemMonitorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="monitor-api@test.local",
            email="monitor-api@test.local",
            password="test-pass",
        )
        self.org = Organization.objects.create(key="monitor-test-org", name="Monitor Test Org")
        Membership.objects.create(
            user=self.user,
            organization=self.org,
            role=Membership.Role.ADMIN,
        )
        self.client.force_authenticate(user=self.user)

    def test_system_monitor_requires_auth(self):
        anon = APIClient()
        resp = anon.get("/api/v1/monitors/system/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_system_monitor_returns_payload(self):
        from apps.monitor.services.interface import collect_and_persist_sample

        collect_and_persist_sample()
        resp = self.client.get("/api/v1/monitors/system/", {"hours": "1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.data
        if isinstance(body, dict) and "data" in body:
            body = body["data"]
        self.assertIn("host", body)
        self.assertIn("series", body)
        self.assertIn("current", body)
        self.assertIn("range", body)
        self.assertGreaterEqual(len(body["series"]), 1)

    def test_invalid_custom_range(self):
        resp = self.client.get("/api/v1/monitors/system/", {"start_at": "2020-01-01T00:00:00Z"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
