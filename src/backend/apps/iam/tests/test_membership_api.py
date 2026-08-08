"""Community Host membership API tests.

Without AuthzProvider, every active affiliation is owner-equivalent
(product: community single-user org; multi-member still all full-power).
Role differentiation and DB owner uniqueness live in the commercial plugin.

These tests force-clear SPI providers so Host community semantics stay
stable even when a local stack has extensions loaded.
"""

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.models import Membership, Organization
from common.extension_spi import clear_providers_for_tests, restore_providers_for_tests


class _CommunitySpiMixin:
    def setUp(self):
        super().setUp()
        self._spi_previous = clear_providers_for_tests()

    def tearDown(self):
        restore_providers_for_tests(self._spi_previous)
        super().tearDown()


class MembershipApiPermissionTests(_CommunitySpiMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = Organization.objects.create(key="acme", name="Acme", is_active=True)
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
        self.target = User.objects.create_user(
            username="member@test.com",
            email="member@test.com",
            password="Pass1234",
        )
        # role= is accepted by QuerySet for plugin sync; community ignores storage.
        Membership.objects.create(
            user=self.owner,
            organization=self.org,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        Membership.objects.create(
            user=self.peer,
            organization=self.org,
            role=Membership.Role.OPERATOR,
            is_active=True,
        )

    def test_any_active_member_can_list_memberships(self):
        """Community: affiliation ⇒ full tenant power (no role column)."""
        self.client.force_authenticate(user=self.peer)
        response = self.client.get(
            reverse("membership-list"),
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]
        self.assertGreaterEqual(payload["pagination"]["total"], 2)

    def test_cannot_assign_owner_role_via_api(self):
        self.client.force_authenticate(user=self.owner)
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

    def test_can_add_member_and_authoritative_role_is_owner(self):
        self.client.force_authenticate(user=self.owner)
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
        from apps.iam.services.membership_service import authoritative_role

        self.assertEqual(authoritative_role(membership), Membership.Role.OWNER)

    def test_cannot_deactivate_last_active_member(self):
        solo = Organization.objects.create(key="solo-deact", name="Solo", is_active=True)
        Membership.objects.create(
            user=self.owner,
            organization=solo,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        owner_membership = Membership.objects.get(user=self.owner, organization=solo)
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            reverse("membership-detail", args=[owner_membership.pk]),
            {"is_active": False},
            format="json",
            HTTP_X_ORG_KEY=solo.key,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_deactivate_peer_when_another_member_remains(self):
        peer_membership = Membership.objects.get(user=self.peer, organization=self.org)
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            reverse("membership-detail", args=[peer_membership.pk]),
            {"is_active": False},
            format="json",
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        peer_membership.refresh_from_db()
        self.assertFalse(peer_membership.is_active)


class ThinAffiliationTests(_CommunitySpiMixin, APITestCase):
    def test_multiple_active_affiliations_allowed_without_role_column(self):
        """Host no longer enforces uniq_iam_org_active_owner; EE owns owner uniqueness."""
        org = Organization.objects.create(key="solo", name="Solo", is_active=True)
        user1 = User.objects.create_user(username="u1@test.com", email="u1@test.com", password="x")
        user2 = User.objects.create_user(username="u2@test.com", email="u2@test.com", password="x")
        Membership.objects.create(
            user=user1,
            organization=org,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        Membership.objects.create(
            user=user2,
            organization=org,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        self.assertEqual(
            Membership.objects.filter(organization=org, is_active=True).count(),
            2,
        )
