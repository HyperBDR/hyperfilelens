from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.models import Membership, Organization
from apps.iam.services.registration_service import provision_registered_user_tenant


class OrgApiScopingTests(APITestCase):
    def setUp(self):
        self.seed_org = Organization.objects.create(
            key="seed-org",
            name="HyperFileLens",
            is_active=True,
        )
        self.seed_user = User.objects.create_user(
            username="admin@hyperfilelens.com",
            email="admin@hyperfilelens.com",
            password="Pass1234",
            is_active=True,
        )
        Membership.objects.create(
            user=self.seed_user,
            organization=self.seed_org,
            role=Membership.Role.OWNER,
            is_active=True,
        )

        self.tenant_user = User.objects.create_user(
            username="2776998293",
            email="2776998293@qq.com",
            password="Pass1234",
            is_active=True,
        )
        self.tenant_org, self.tenant_membership = provision_registered_user_tenant(self.tenant_user)

    def test_orgs_list_is_scoped_to_current_user(self):
        self.client.force_authenticate(user=self.tenant_user)

        response = self.client.get(reverse("org-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        org_keys = [item["key"] for item in response.data["data"]["list"]]
        self.assertEqual(org_keys, [self.tenant_org.key])

    def test_memberships_list_is_scoped_to_current_user_org(self):
        self.client.force_authenticate(user=self.tenant_user)

        response = self.client.get(
            reverse("membership-list"),
            HTTP_X_ORG_KEY=self.tenant_org.key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["data"]["list"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user"], self.tenant_user.id)
        self.assertEqual(rows[0]["organization"], self.tenant_org.id)
        self.assertEqual(rows[0]["role"], Membership.Role.OWNER)

    def test_orgs_list_honors_x_org_key(self):
        self.client.force_authenticate(user=self.tenant_user)

        response = self.client.get(
            reverse("org-list"),
            HTTP_X_ORG_KEY=self.tenant_org.key,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        org_list = response.data["data"]["list"]
        self.assertEqual(len(org_list), 1)
        self.assertEqual(org_list[0]["key"], self.tenant_org.key)

        wrong_org_response = self.client.get(
            reverse("org-list"),
            HTTP_X_ORG_KEY=self.seed_org.key,
        )
        self.assertEqual(wrong_org_response.status_code, status.HTTP_200_OK)
        self.assertEqual(wrong_org_response.data["data"]["list"], [])
