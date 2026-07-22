from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.alert.constants import AlertSeverity, AlertStatus, AlertType
from apps.alert.models import AlertRecord
from apps.iam.models import Membership, Organization
from apps.node.models import Node, NodeRole
from apps.task.models import Task


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsOrgsApiTest(TestCase):
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
        self.owner = User.objects.create_user(
            username="owner@test.com",
            email="owner@test.com",
            password="Pass1234",
        )
        Membership.objects.create(
            user=self.owner,
            organization=self.org,
            role=Membership.Role.OWNER,
        )

    def test_list_orgs(self):
        Organization.objects.create(key="__platform_lens__", name="Platform Lens")
        response = self.client.get("/api/v1/platform-ops/orgs")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertGreaterEqual(payload["count"], 1)
        row = next(r for r in payload["results"] if r["key"] == "acme")
        self.assertEqual(row["owner_email"], "owner@test.com")
        self.assertEqual(row["owner_user_id"], self.owner.pk)
        self.assertEqual(row["member_count"], 1)
        self.assertEqual(row["node_count"], 0)
        self.assertEqual(row["failed_task_count"], 0)
        self.assertEqual(row["incident_count"], 0)
        self.assertGreaterEqual(payload["stats"]["active"], 1)
        self.assertFalse(
            any(row["key"] == "__platform_lens__" for row in payload["results"])
        )

    def test_list_orgs_supports_health_status_and_owner_search(self):
        Node.objects.create(
            organization=self.org,
            name="agent-1",
            role=NodeRole.AGENT,
            status=Node.Status.ONLINE,
        )
        Task.objects.create(
            organization_id=self.org.pk,
            task_type=Task.Type.BACKUP,
            display_name="Failed backup",
            status=Task.Status.FAILED,
        )
        AlertRecord.objects.create(
            organization=self.org,
            type=AlertType.SYSTEM,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.FIRING,
            title="Customer incident",
            fingerprint="customer-incident",
        )

        response = self.client.get(
            "/api/v1/platform-ops/orgs",
            {"health": "attention", "status": "active", "search": "owner@test.com"},
        )

        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["count"], 1)
        row = payload["results"][0]
        self.assertEqual(row["node_count"], 1)
        self.assertEqual(row["failed_task_count"], 1)
        self.assertEqual(row["incident_count"], 1)
        self.assertEqual(payload["stats"]["with_incidents"], 1)

    def test_org_detail_includes_memberships(self):
        response = self.client.get(f"/api/v1/platform-ops/orgs/{self.org.pk}")
        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["key"], "acme")
        self.assertEqual(len(payload["memberships"]), 1)
        self.assertEqual(payload["memberships"][0]["user_email"], "owner@test.com")
        self.assertEqual(payload["memberships"][0]["user_display_name"], "owner@test.com")

    def test_delete_org(self):
        org = Organization.objects.create(key="delete-me", name="Delete Me")
        response = self.client.delete(f"/api/v1/platform-ops/orgs/{org.pk}")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Organization.objects.filter(pk=org.pk).exists())

    def test_create_org_rejects_owner_with_existing_organization(self):
        response = self.client.post(
            "/api/v1/platform-ops/orgs",
            {
                "key": "second-org",
                "name": "Second Organization",
                "owner_user_id": self.owner.pk,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Organization.objects.filter(key="second-org").exists())
