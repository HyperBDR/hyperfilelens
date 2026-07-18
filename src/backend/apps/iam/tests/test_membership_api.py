from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.models import Membership, Organization


class MembershipApiPermissionTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="acme", name="Acme", is_active=True)
        self.owner = User.objects.create_user(
            username="owner@test.com",
            email="owner@test.com",
            password="Pass1234",
        )
        self.admin = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="Pass1234",
        )
        self.operator = User.objects.create_user(
            username="operator@test.com",
            email="operator@test.com",
            password="Pass1234",
        )
        self.target = User.objects.create_user(
            username="member@test.com",
            email="member@test.com",
            password="Pass1234",
        )
        Membership.objects.create(
            user=self.owner,
            organization=self.org,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        Membership.objects.create(
            user=self.admin,
            organization=self.org,
            role=Membership.Role.ADMIN,
            is_active=True,
        )
        Membership.objects.create(
            user=self.operator,
            organization=self.org,
            role=Membership.Role.OPERATOR,
            is_active=True,
        )

    def test_operator_cannot_list_memberships(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.get(
            reverse("membership-list"),
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_org_memberships(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(
            reverse("membership-list"),
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]
        self.assertGreaterEqual(payload["pagination"]["total"], 3)
        self.assertGreaterEqual(len(payload["list"]), 1)

    def test_admin_cannot_assign_owner_role(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("membership-list"),
            {
                "user": self.target.pk,
                "role": Membership.Role.OWNER,
                "is_active": True,
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_add_operator(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            reverse("membership-list"),
            {
                "user": self.target.pk,
                "role": Membership.Role.OPERATOR,
                "is_active": True,
            },
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        membership = Membership.objects.get(user=self.target, organization=self.org)
        self.assertEqual(membership.role, Membership.Role.OPERATOR)

    def test_cannot_deactivate_owner(self):
        owner_membership = Membership.objects.get(user=self.owner, organization=self.org)
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            reverse("membership-detail", args=[owner_membership.pk]),
            {"is_active": False},
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OwnerUniquenessTests(APITestCase):
    def test_only_one_active_owner_per_org(self):
        org = Organization.objects.create(key="solo", name="Solo", is_active=True)
        user1 = User.objects.create_user(username="u1@test.com", email="u1@test.com", password="x")
        user2 = User.objects.create_user(username="u2@test.com", email="u2@test.com", password="x")
        Membership.objects.create(
            user=user1,
            organization=org,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Membership.objects.create(
                user=user2,
                organization=org,
                role=Membership.Role.OWNER,
                is_active=True,
            )
