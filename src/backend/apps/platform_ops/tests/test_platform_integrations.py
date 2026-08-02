from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsIntegrationsApiTest(TestCase):
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

    @patch(
        "apps.platform_ops.api.views.platform.lens_deploy.sourcelens_console_url",
        return_value="https://console.example.com:11445",
    )
    @patch(
        "apps.platform_ops.api.views.platform.lens_deploy.sourcelens_version",
        return_value="v0.20.0",
    )
    @patch(
        "apps.platform_ops.api.views.platform.sl_client.ping",
        return_value={
            "configured": True,
            "reachable": True,
            "authenticated": True,
            "business_ready": True,
            "status": "ready",
            "warning": "",
        },
    )
    def test_sourcelens_entry_exposes_console_metadata(
        self, _ping, _version, _console_url
    ):
        response = self.client.get("/api/v1/platform-ops/platform/integrations")

        self.assertEqual(response.status_code, 200)
        integration = _payload(response)["integrations"][0]
        self.assertEqual(integration["key"], "sourcelens")
        self.assertEqual(integration["version"], "v0.20.0")
        self.assertEqual(
            integration["console_url"],
            "https://console.example.com:11445",
        )
        self.assertTrue(integration["reachable"])
        self.assertTrue(integration["authenticated"])
        self.assertTrue(integration["business_ready"])
        self.assertEqual(integration["status"], "ready")
        self.assertTrue(integration["checked_at"])
