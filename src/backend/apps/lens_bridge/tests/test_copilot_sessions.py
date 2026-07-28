import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.iam.services.registration_service import provision_registered_user_tenant
from apps.lens_bridge.models import LensSessionLink, LensSlUserLink, LensUsageLedger


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
        self.assertEqual(payload["run_outcomes"], [])

    @patch("apps.lens_bridge.services.sl_client.request_json")
    def test_sync_returns_a_durable_sanitized_failed_run_outcome(self, request_json):
        run_uuid = uuid.uuid4()
        session_uuid = uuid.uuid4()
        self.session.lifecycle_status = LensSessionLink.LifecycleStatus.READY
        self.session.provision_phase = LensSessionLink.ProvisionPhase.READY
        self.session.sl_session_uuid = session_uuid
        self.session.active_run_uuid = run_uuid
        self.session.active_run_status = "running"
        self.session.save(
            update_fields=[
                "lifecycle_status",
                "provision_phase",
                "sl_session_uuid",
                "active_run_uuid",
                "active_run_status",
                "updated_at",
            ]
        )
        LensSlUserLink.objects.create(
            hfl_user=self.user,
            sl_user_id=41,
            sl_username="hfl-u-41",
            provision_status=LensSlUserLink.ProvisionStatus.READY,
        )
        LensUsageLedger.objects.create(
            organization=self.org,
            hfl_user=self.user,
            session_link=self.session,
            sl_user_id=41,
            sl_run_uuid=run_uuid,
            run_status="running",
            question="List files",
            occurred_at=self.session.created_at,
        )

        def response_for(_method, path, **_kwargs):
            if path.endswith("/messages/"):
                return [
                    {
                        "uuid": str(uuid.uuid4()),
                        "role": "user",
                        "content": "List files",
                        "run": str(run_uuid),
                    }
                ]
            if path.endswith(f"/runs/{run_uuid}/"):
                return {
                    "uuid": str(run_uuid),
                    "status": "failed",
                    "error": "MODEL_STREAM_ERROR api_key=must-not-leak",
                }
            raise AssertionError(path)

        request_json.side_effect = response_for
        response = self.client.get(
            reverse("lens-copilot-session-sync", kwargs={"pk": self.session.pk}),
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        payload = payload.get("data", payload)
        self.assertIsNone(payload["active_run"])
        self.assertEqual(len(payload["run_outcomes"]), 1)
        outcome = payload["run_outcomes"][0]
        self.assertEqual(outcome["run_uuid"], str(run_uuid))
        self.assertEqual(outcome["status"], "failed")
        self.assertEqual(outcome["error_code"], "MODEL_PROVIDER_ERROR")
        self.assertIn("quota", outcome["message"])
        self.assertNotIn("must-not-leak", str(payload))
        self.session.refresh_from_db()
        self.assertIsNone(self.session.active_run_uuid)
