from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.iam.services.registration_service import provision_registered_user_tenant
from django.contrib.auth import get_user_model

User = get_user_model()


class LensBridgeHealthTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lens-bridge@test.local",
            email="lens-bridge@test.local",
            password="Pass1234",
            is_active=True,
        )
        self.org, _ = provision_registered_user_tenant(self.user)

    def test_health_ok_when_unconfigured(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("lens-bridge-health"),
            HTTP_X_ORG_KEY=self.org.key,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["app"], "lens_bridge")
        self.assertIn("lens", response.json())
