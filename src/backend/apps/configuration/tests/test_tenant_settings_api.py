"""Tests for tenant organization settings API."""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.configuration.models import GlobalConfig
from apps.configuration.tenant_conf import CONFIG_KEY_DR_TASK_CONCURRENCY
from apps.iam.models import Membership, Organization


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class OrgSettingsApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(key="acme", name="Acme")
        self.owner = User.objects.create_user(
            username="owner@test.com",
            email="owner@test.com",
            password="Pass1234",
        )
        self.auditor = User.objects.create_user(
            username="auditor@test.com",
            email="auditor@test.com",
            password="Pass1234",
        )
        Membership.objects.create(
            user=self.owner,
            organization=self.org,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            user=self.auditor,
            organization=self.org,
            role=Membership.Role.AUDITOR,
        )

    def test_owner_reads_effective_default(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            "/api/v1/configuration/org-settings/",
            HTTP_X_ORG_KEY="acme",
        )
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["org_key"], "acme")
        row = payload["settings"][0]
        self.assertEqual(row["key"], CONFIG_KEY_DR_TASK_CONCURRENCY)
        self.assertEqual(row["value_source"], "default")

    def test_owner_saves_tenant_override(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            "/api/v1/configuration/org-settings/",
            {
                "settings": [
                    {"key": CONFIG_KEY_DR_TASK_CONCURRENCY, "value": 16},
                ]
            },
            format="json",
            HTTP_X_ORG_KEY="acme",
        )
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        row = payload["settings"][0]
        self.assertEqual(row["value"], 16)
        self.assertEqual(row["value_source"], "tenant")
        self.assertTrue(
            GlobalConfig.objects.filter(
                key=CONFIG_KEY_DR_TASK_CONCURRENCY,
                scope=GlobalConfig.Scope.TENANT,
                tenant_key="acme",
            ).exists()
        )

    def test_auditor_cannot_write(self):
        self.client.force_authenticate(user=self.auditor)
        response = self.client.patch(
            "/api/v1/configuration/org-settings/",
            {
                "settings": [
                    {"key": CONFIG_KEY_DR_TASK_CONCURRENCY, "value": 8},
                ]
            },
            format="json",
            HTTP_X_ORG_KEY="acme",
        )
        self.assertEqual(response.status_code, 403)

    def test_inherits_global_when_no_tenant_row(self):
        GlobalConfig.objects.create(
            key=CONFIG_KEY_DR_TASK_CONCURRENCY,
            scope=GlobalConfig.Scope.GLOBAL,
            tenant_key="",
            value_type=GlobalConfig.ValueType.NUMBER,
            category="file_dr",
            value=20,
            is_active=True,
        )
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            "/api/v1/configuration/org-settings/",
            HTTP_X_ORG_KEY="acme",
        )
        payload = _payload(response)
        row = payload["settings"][0]
        self.assertEqual(row["value"], 20)
        self.assertEqual(row["value_source"], "global")
