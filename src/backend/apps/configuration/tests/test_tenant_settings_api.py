"""Tests for tenant organization settings API (Community Host).

Without AuthzProvider, every active affiliation is owner-equivalent.
Role-limited writes (auditor 403) are covered by the commercial plugin.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.configuration.models import GlobalConfig
from apps.configuration.tenant_conf import CONFIG_KEY_DR_TASK_CONCURRENCY
from apps.iam.models import Membership, Organization
from common.extension_spi import clear_providers_for_tests, restore_providers_for_tests


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


class OrgSettingsApiTest(TestCase):
    def setUp(self):
        self._spi_previous = clear_providers_for_tests()
        self.client = APIClient()
        self.org = Organization.objects.create(key="acme", name="Acme")
        self.owner = User.objects.create_user(
            username="owner@test.com",
            email="owner@test.com",
            password="Pass1234",
        )
        self.peer = User.objects.create_user(
            username="peer@test.com",
            email="peer@test.com",
            password="Pass1234",
        )
        # role= is accepted for plugin sync; community ignores storage for authz.
        Membership.objects.create(
            user=self.owner,
            organization=self.org,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            user=self.peer,
            organization=self.org,
            role=Membership.Role.AUDITOR,
        )

    def tearDown(self):
        restore_providers_for_tests(self._spi_previous)

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

    def test_community_member_write_is_owner_equivalent(self):
        """Community: affiliation ⇒ full tenant power (role kwarg does not limit)."""
        self.client.force_authenticate(user=self.peer)
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
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["settings"][0]["value"], 8)

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
