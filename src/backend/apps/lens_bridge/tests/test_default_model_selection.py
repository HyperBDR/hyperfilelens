from __future__ import annotations

import uuid
from unittest.mock import patch

from django.test import TestCase

from apps.iam.models import Organization
from apps.lens_bridge.models import LensOrgLink, LensOrgModelLink
from apps.lens_bridge.services import deployment_ai_model, platform_lens, provisioning


class DefaultModelSelectionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="tenant-one", name="Tenant One")

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_source_lens_explicit_default_wins_over_list_order(self, active_configs):
        active_configs.return_value = [
            {"uuid": "first", "is_active": True},
            {"uuid": "selected", "is_active": True, "is_default": True},
        ]

        self.assertEqual(
            provisioning.default_model_ref_for_org(self.org),
            "selected",
        )

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_tenant_explicit_default_wins_over_platform_default(self, active_configs):
        tenant_uuid = uuid.UUID("7f65ac13-a16e-4db9-9479-e43818bbb7aa")
        LensOrgModelLink.objects.create(
            organization=self.org,
            sl_config_uuid=tenant_uuid,
        )
        LensOrgLink.objects.create(
            organization=self.org,
            default_agent_model_ref=tenant_uuid,
        )
        active_configs.return_value = [
            {"uuid": "platform", "is_active": True, "is_default": True},
            {"uuid": str(tenant_uuid), "is_active": True},
        ]

        self.assertEqual(
            provisioning.default_model_ref_for_org(self.org),
            str(tenant_uuid),
        )

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_managed_model_is_fallback_when_no_explicit_default(self, active_configs):
        managed_uuid = uuid.UUID("cf992c95-1919-4719-b52a-f50f3f97eb08")
        platform_org = platform_lens.get_or_create_platform_org()
        LensOrgModelLink.objects.create(
            organization=platform_org,
            sl_config_uuid=managed_uuid,
            management_key=deployment_ai_model.DEPLOYMENT_MODEL_MANAGEMENT_KEY,
        )
        active_configs.return_value = [
            {"uuid": "first", "is_active": True},
            {"uuid": str(managed_uuid), "is_active": True},
        ]

        self.assertEqual(
            provisioning.default_model_ref_for_org(self.org),
            str(managed_uuid),
        )

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_tracked_platform_default_wins_over_source_lens_list_order(
        self,
        active_configs,
    ):
        selected_uuid = uuid.UUID("c71343af-96f3-4116-8807-1661982e77a8")
        platform_org = platform_lens.get_or_create_platform_org()
        LensOrgLink.objects.create(
            organization=platform_org,
            default_agent_model_ref=selected_uuid,
        )
        active_configs.return_value = [
            {"uuid": "derived-first", "is_active": True, "is_default": True},
            {"uuid": str(selected_uuid), "is_active": True},
        ]

        self.assertEqual(
            provisioning.default_model_ref_for_org(self.org),
            str(selected_uuid),
        )
