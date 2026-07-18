from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.iam.models import Membership, Organization
from apps.monitor.services.interface import collect_and_persist_sample


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsMonitoringApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        self.staff = User.objects.create_user(
            username="staff@test.com",
            email="staff@test.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.org = Organization.objects.create(key="acme", name="Acme")
        Membership.objects.create(
            user=self.staff,
            organization=self.org,
            role=Membership.Role.OWNER,
        )

    def test_overview_ok(self):
        response = self.client.get("/api/v1/platform-ops/")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("metrics", payload)

    def test_monitoring_tasks_ok(self):
        response = self.client.get("/api/v1/platform-ops/monitoring/tasks")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("results", payload)

    def test_monitoring_notifications_ok(self):
        response = self.client.get("/api/v1/platform-ops/monitoring/notifications")
        self.assertEqual(response.status_code, 200)

    def test_platform_environment_ok(self):
        response = self.client.get("/api/v1/platform-ops/platform/settings/environment")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("effective", payload)
        self.assertIn("health", payload)

    def test_platform_agent_releases_ok(self):
        response = self.client.get("/api/v1/platform-ops/platform/agent-releases")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("results", payload)
        self.assertIn("count", payload)
        self.assertIn("bootstrap", payload)
        self.assertIn("active_source", payload["bootstrap"])

    def test_platform_notification_channels_ok(self):
        response = self.client.get("/api/v1/platform-ops/platform/notification-channels")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("results", payload)
        self.assertIn("count", payload)

    def test_monitoring_host_ok(self):
        collect_and_persist_sample()
        response = self.client.get("/api/v1/platform-ops/monitoring/host", {"hours": "1"})
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertIn("host", payload)
        self.assertIn("series", payload)
        self.assertIn("current", payload)

    def test_system_audit_ok(self):
        response = self.client.get("/api/v1/platform-ops/system/audit")
        self.assertEqual(response.status_code, 200)
