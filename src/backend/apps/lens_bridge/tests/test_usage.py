import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.iam.models import Membership
from apps.iam.services.registration_service import provision_registered_user_tenant
from apps.lens_bridge.models import LensSessionLink, LensSlUserLink, LensUsageLedger
from apps.lens_bridge.services import usage


class UsageCaptureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="usage-capture",
            email="usage-capture@example.com",
            password="test-password",
        )
        self.org, _ = provision_registered_user_tenant(self.user)
        LensSlUserLink.objects.create(
            hfl_user=self.user,
            sl_user_id=23,
            sl_username="hfl-u-23",
            provision_status=LensSlUserLink.ProvisionStatus.READY,
        )
        self.session = LensSessionLink.objects.create(
            organization=self.org,
            hfl_user=self.user,
            title="Finance Chat",
            source_scopes_json=[{"source_path": "/finance", "path_type": "dir"}],
        )

    def test_captures_all_model_calls_for_one_q_and_a(self):
        run_uuid = uuid.uuid4()
        usage.register_usage_run(
            self.session,
            run_uuid=run_uuid,
            question="Summarize finance files",
            status="running",
        )

        row = usage.capture_run_usage(
            self.session,
            {
                "uuid": str(run_uuid),
                "status": "done",
                "started_at": timezone.now().isoformat(),
                "finished_at": timezone.now().isoformat(),
                "steps": [
                    {
                        "detail": {
                            "events": [
                                {
                                    "agent_event": "llm.response",
                                    "prompt_tokens": 100,
                                    "completion_tokens": 20,
                                    "total_tokens": 120,
                                    "cost": 0.01,
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 30,
                                "completion_tokens": 5,
                                "total_tokens": 35,
                                "cost": 0.002,
                            },
                        }
                    }
                ],
            },
        )

        self.assertIsNotNone(row)
        self.assertEqual(row.prompt_tokens, 130)
        self.assertEqual(row.completion_tokens, 25)
        self.assertEqual(row.total_tokens, 155)
        self.assertEqual(row.model_calls, 2)
        self.assertEqual(row.estimated_cost, Decimal("0.012"))
        self.assertEqual(len(row.call_details_json), 2)


class UsageApiIsolationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="usage-owner",
            email="usage-owner@example.com",
            password="test-password",
        )
        self.org, _ = provision_registered_user_tenant(self.user)
        self.other_user = get_user_model().objects.create_user(
            username="usage-other",
            email="usage-other@example.com",
            password="test-password",
        )
        Membership.objects.create(
            user=self.other_user,
            organization=self.org,
            role=Membership.Role.OPERATOR,
        )
        LensSlUserLink.objects.create(
            hfl_user=self.user,
            sl_user_id=23,
            sl_username="hfl-u-23",
            provision_status=LensSlUserLink.ProvisionStatus.READY,
        )
        self.other_row = LensUsageLedger.objects.create(
            organization=self.org,
            hfl_user=self.other_user,
            sl_user_id=24,
            sl_run_uuid=uuid.uuid4(),
            chat_title="Other User Chat",
            question="Private question",
            occurred_at=timezone.now(),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("apps.lens_bridge.services.usage.sl_client.request_json")
    def test_admin_run_queries_are_forced_to_current_sl_user(self, request_json):
        exact_uuid = uuid.uuid4()

        def response_for(_method, path, **_kwargs):
            return {
                "results": [
                    {
                        "uuid": str(exact_uuid),
                        "username": "hfl-u-23",
                        "question": "My usage",
                        "status": "done",
                        "total_tokens": 1200,
                        "prompt_tokens": 1000,
                        "completion_tokens": 200,
                        "total_cost": 0.25,
                        "created_at": timezone.now().isoformat(),
                    },
                    {
                        "uuid": str(uuid.uuid4()),
                        "username": "hfl-u-230",
                        "question": "Fuzzy username must not leak",
                        "status": "done",
                        "total_tokens": 9999,
                        "created_at": timezone.now().isoformat(),
                    },
                ],
                "total": 2,
            }

        request_json.side_effect = response_for
        response = self.client.get(
            reverse("lens-copilot-usage"),
            {"user_id": "999", "page_size": 20},
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        payload = payload.get("data", payload)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["results"][0]["question"], "My usage")
        self.assertNotIn("Private question", str(payload))
        run_params = request_json.call_args_list[0].kwargs["params"]
        self.assertEqual(run_params["username"], "hfl-u-23")
        self.assertNotEqual(run_params["username"], "999")

    def test_detail_does_not_expose_another_users_ledger(self):
        response = self.client.get(
            reverse("lens-copilot-usage-detail", kwargs={"run_uuid": self.other_row.sl_run_uuid}),
            HTTP_X_ORG_KEY=self.org.key,
        )

        self.assertEqual(response.status_code, 404)

    @patch("apps.lens_bridge.services.usage.backfill_usage_ledgers")
    def test_today_overview_aggregates_model_calls_and_hourly_trend(self, _backfill):
        now = timezone.localtime()
        LensUsageLedger.objects.create(
            organization=self.org,
            hfl_user=self.user,
            sl_user_id=23,
            sl_run_uuid=uuid.uuid4(),
            chat_title="Finance Chat",
            backup_source_name="Finance Server",
            question="Summarize today's changes",
            prompt_tokens=100,
            completion_tokens=25,
            cached_tokens=20,
            reasoning_tokens=5,
            total_tokens=125,
            model_calls=3,
            estimated_cost=Decimal("0.0125"),
            occurred_at=now,
        )

        payload = usage.usage_overview(self.org, self.user, {})

        self.assertEqual(payload["period"]["start_date"], now.date().isoformat())
        self.assertEqual(payload["period"]["end_date"], now.date().isoformat())
        self.assertEqual(payload["summary"]["model_calls"], 3)
        self.assertEqual(payload["summary"]["q_and_a_requests"], 1)
        self.assertEqual(payload["by_backup_source"][0]["model_calls"], 3)
        self.assertEqual(len(payload["trend"]), now.hour + 1)
        self.assertTrue(all("T" in row["bucket"] for row in payload["trend"]))
        current_hour = payload["trend"][now.hour]
        self.assertEqual(current_hour["total_calls"], 3)
        self.assertEqual(current_hour["total_tokens"], 125)
