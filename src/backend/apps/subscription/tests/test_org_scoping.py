from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.services.registration_service import provision_registered_user_tenant
from apps.subscription.models import Entitlement, OrganizationSubscription, Plan

User = get_user_model()


class SubscriptionOrgScopingTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="sub-a@test.local",
            email="sub-a@test.local",
            password="Pass1234",
            is_active=True,
        )
        self.org_a, _ = provision_registered_user_tenant(self.user_a)

        self.user_b = User.objects.create_user(
            username="sub-b@test.local",
            email="sub-b@test.local",
            password="Pass1234",
            is_active=True,
        )
        self.org_b, _ = provision_registered_user_tenant(self.user_b)

        self.plan = Plan.objects.create(key="standard", name="Standard")
        OrganizationSubscription.objects.create(
            organization=self.org_a,
            plan=self.plan,
        )
        OrganizationSubscription.objects.create(
            organization=self.org_b,
            plan=self.plan,
        )
        self.entitlement_a = Entitlement.objects.create(
            organization=self.org_a,
            key="backup",
        )
        self.entitlement_b = Entitlement.objects.create(
            organization=self.org_b,
            key="backup",
        )

    def test_entitlement_list_scoped_to_org(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            reverse("entitlement-list"),
            HTTP_X_ORG_KEY=self.org_a.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [self.entitlement_a.id])

    def test_entitlement_foreign_org_detail_404(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            reverse("entitlement-detail", kwargs={"pk": self.entitlement_b.id}),
            HTTP_X_ORG_KEY=self.org_a.key,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
