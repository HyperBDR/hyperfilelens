from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.iam.services.registration_service import provision_registered_user_tenant
from apps.lens_bridge.models import LensSessionLink


class CopilotSessionApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="copilot-session-owner",
            email="copilot-session-owner@example.com",
            password="test-password",
        )
        self.org, _ = provision_registered_user_tenant(self.user)
        self.session = LensSessionLink.objects.create(
            organization=self.org,
            hfl_user=self.user,
            title="Preparing Chat",
            lifecycle_status=LensSessionLink.LifecycleStatus.PROVISIONING,
            provision_phase=LensSessionLink.ProvisionPhase.QUEUED,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_sync_resolves_the_current_users_session(self):
        response = self.client.get(
            reverse(
                "lens-copilot-session-sync",
                kwargs={"pk": self.session.pk},
            ),
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        payload = payload.get("data", payload)
        self.assertEqual(payload["session_id"], self.session.pk)
        self.assertEqual(
            payload["lifecycle_status"],
            LensSessionLink.LifecycleStatus.PROVISIONING,
        )
