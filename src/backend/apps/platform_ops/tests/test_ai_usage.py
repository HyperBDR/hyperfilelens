from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.iam.models import Organization
from apps.lens_bridge.models import LensUsageLedger


def _payload(response):
    data = response.data
    if isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsAiUsageTests(TestCase):
    path = "/api/v1/platform-ops/lens/usage"

    def setUp(self):
        self.client = APIClient()
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        self.staff = User.objects.create_user(
            username="ai-usage-admin@example.com",
            email="ai-usage-admin@example.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.acme = Organization.objects.create(key="acme", name="Acme")
        self.beta = Organization.objects.create(key="beta", name="Beta")
        self.acme_user = User.objects.create_user(
            username="acme@example.com",
            email="acme@example.com",
        )
        self.beta_user = User.objects.create_user(
            username="beta@example.com",
            email="beta@example.com",
        )
        now = timezone.now()
        LensUsageLedger.objects.create(
            organization=self.acme,
            hfl_user=self.acme_user,
            sl_user_id=10,
            sl_run_uuid=uuid.uuid4(),
            question="Summarize finance",
            run_status="done",
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            model_calls=2,
            estimated_cost=Decimal("0.012"),
            occurred_at=now,
        )
        LensUsageLedger.objects.create(
            organization=self.beta,
            hfl_user=self.beta_user,
            sl_user_id=11,
            sl_run_uuid=uuid.uuid4(),
            question="Find failed backups",
            run_status="failed",
            prompt_tokens=50,
            completion_tokens=10,
            total_tokens=60,
            model_calls=1,
            estimated_cost=Decimal("0.006"),
            occurred_at=now,
        )
        LensUsageLedger.objects.create(
            organization=self.acme,
            hfl_user=self.acme_user,
            sl_user_id=10,
            sl_run_uuid=uuid.uuid4(),
            question="Old request",
            run_status="done",
            total_tokens=999,
            occurred_at=now - timedelta(days=2),
        )

    def test_returns_platform_wide_usage(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["summary"]["requests"], 2)
        self.assertEqual(payload["summary"]["organizations"], 2)
        self.assertEqual(payload["summary"]["users"], 2)
        self.assertEqual(payload["summary"]["total_tokens"], 180)
        self.assertEqual(payload["summary"]["model_calls"], 3)
        self.assertEqual(payload["summary"]["success_rate"], 50.0)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(len(payload["by_organization"]), 2)

    def test_filters_by_organization_and_search(self):
        response = self.client.get(
            self.path,
            {"org": "acme", "search": "finance"},
        )

        self.assertEqual(response.status_code, 200)
        payload = _payload(response)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["organization_key"], "acme")
        self.assertEqual(payload["results"][0]["user_email"], "acme@example.com")
        self.assertEqual(payload["summary"]["success_rate"], 100.0)
