from __future__ import annotations

import uuid
from unittest.mock import patch

from django.test import TestCase

from apps.iam.models import Organization
from apps.lens_bridge.models import LensOrgLink, LensOrgModelLink
from apps.lens_bridge.services import (
    deployment_ai_model,
    org_models,
    platform_lens,
    provisioning,
)


class DefaultModelSelectionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(key="tenant-one", name="Tenant One")

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_source_lens_global_default_is_not_an_hfl_role_default(
        self,
        active_configs,
    ):
        active_configs.return_value = [
            {"uuid": "first", "is_active": True},
            {"uuid": "selected", "is_active": True, "is_default": True},
        ]

        self.assertIsNone(provisioning.default_model_ref_for_org(self.org))

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_unlinked_tenant_model_is_never_used_as_platform_fallback(
        self,
        active_configs,
    ):
        other_org = Organization.objects.create(
            key="tenant-two",
            name="Tenant Two",
        )
        other_uuid = uuid.uuid4()
        LensOrgModelLink.objects.create(
            organization=other_org,
            sl_config_uuid=other_uuid,
        )
        active_configs.return_value = [
            {
                "uuid": str(other_uuid),
                "is_active": True,
                "is_default": True,
            }
        ]

        self.assertIsNone(provisioning.default_model_ref_for_org(self.org))

    def test_historical_deployment_model_is_removed_from_persisted_default(
        self,
    ):
        historical_uuid = uuid.UUID(
            "d62e2224-34f5-47c3-a7b4-9ca04a2d95df"
        )
        LensOrgModelLink.objects.create(
            organization=self.org,
            sl_config_uuid=historical_uuid,
            management_key=f"deploy-agent-history-{historical_uuid.hex}",
            deployment_role=LensOrgModelLink.DeploymentRole.AGENT,
            is_deployment_history=True,
        )
        org_link = LensOrgLink.objects.create(
            organization=self.org,
            default_agent_model_ref=historical_uuid,
        )

        repaired = org_models.ensure_org_default_model(self.org)

        org_link.refresh_from_db()
        self.assertIsNone(repaired.default_agent_model_ref)
        self.assertIsNone(org_link.default_agent_model_ref)

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
    def test_multimodal_default_is_resolved_without_becoming_agent(
        self,
        active_configs,
    ):
        multimodal_uuid = uuid.UUID(
            "f658a5ed-8878-4c81-8428-87a3926203ab"
        )
        platform_org = platform_lens.get_or_create_platform_org()
        LensOrgModelLink.objects.create(
            organization=platform_org,
            sl_config_uuid=multimodal_uuid,
            management_key=deployment_ai_model.DEPLOYMENT_MULTIMODAL_MODEL_MANAGEMENT_KEY,
        )
        LensOrgLink.objects.create(
            organization=platform_org,
            default_multimodal_model_ref=multimodal_uuid,
        )
        active_configs.return_value = [
            {"uuid": str(multimodal_uuid), "is_active": True},
        ]

        self.assertIsNone(
            provisioning.default_model_ref_for_org(self.org)
        )
        self.assertEqual(
            provisioning.default_multimodal_model_ref_for_org(self.org),
            str(multimodal_uuid),
        )

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_historical_multimodal_model_never_becomes_agent_fallback(
        self,
        active_configs,
    ):
        historical_uuid = uuid.UUID(
            "719502e8-b0b4-4ce8-8837-d2fbcb007327"
        )
        agent_uuid = uuid.UUID("fdb181b5-cf04-411a-83da-897fe571365e")
        platform_org = platform_lens.get_or_create_platform_org()
        LensOrgModelLink.objects.create(
            organization=platform_org,
            sl_config_uuid=historical_uuid,
            management_key=f"deploy-multimodal-history-{historical_uuid.hex}",
            deployment_role=LensOrgModelLink.DeploymentRole.MULTIMODAL,
            is_deployment_history=True,
        )
        LensOrgModelLink.objects.create(
            organization=platform_org,
            sl_config_uuid=agent_uuid,
        )
        active_configs.return_value = [
            {
                "uuid": str(historical_uuid),
                "is_active": True,
                "is_default": True,
                "is_deployment_history": True,
            },
            {"uuid": str(agent_uuid), "is_active": True},
        ]

        self.assertEqual(
            provisioning.default_model_ref_for_org(self.org),
            str(agent_uuid),
        )

    @patch("apps.lens_bridge.services.org_models.active_llm_configs")
    def test_tracked_platform_default_wins_over_source_lens_list_order(
        self,
        active_configs,
    ):
        selected_uuid = uuid.UUID("c71343af-96f3-4116-8807-1661982e77a8")
        platform_org = platform_lens.get_or_create_platform_org()
        LensOrgModelLink.objects.create(
            organization=platform_org,
            sl_config_uuid=selected_uuid,
        )
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

    @patch("apps.lens_bridge.services.org_models.sl_client.request_json")
    def test_org_model_catalog_filters_global_source_lens_rows(
        self,
        request_json,
    ):
        own_uuid = uuid.uuid4()
        other_uuid = uuid.uuid4()
        other_org = Organization.objects.create(
            key="catalog-tenant-two",
            name="Catalog Tenant Two",
        )
        LensOrgModelLink.objects.create(
            organization=self.org,
            sl_config_uuid=own_uuid,
        )
        LensOrgModelLink.objects.create(
            organization=other_org,
            sl_config_uuid=other_uuid,
        )
        request_json.return_value = [
            {"uuid": str(own_uuid), "is_active": True},
            {"uuid": str(other_uuid), "is_active": True},
        ]

        rows = org_models.active_llm_configs(org=self.org)

        self.assertEqual(
            [str(row["uuid"]) for row in rows],
            [str(own_uuid)],
        )
        request_json.assert_called_once_with(
            "GET",
            "/api/v1/admin/llm-config/",
        )

    @patch("apps.lens_bridge.services.org_models.sl_client.request_json")
    def test_platform_catalog_can_display_unlinked_tenant_rows(
        self,
        request_json,
    ):
        platform_org = platform_lens.get_or_create_platform_org()
        platform_uuid = uuid.uuid4()
        tenant_uuid = uuid.uuid4()
        LensOrgModelLink.objects.create(
            organization=platform_org,
            sl_config_uuid=platform_uuid,
        )
        LensOrgModelLink.objects.create(
            organization=self.org,
            sl_config_uuid=tenant_uuid,
        )
        request_json.return_value = [
            {"uuid": str(platform_uuid), "is_active": True},
            {"uuid": str(tenant_uuid), "is_active": True},
        ]

        rows = org_models.list_all_llm_configs(org=platform_org)

        self.assertEqual(len(rows), 2)
        tenant_row = next(
            row for row in rows if row["uuid"] == str(tenant_uuid)
        )
        self.assertFalse(tenant_row["is_default_agent"])
        self.assertFalse(tenant_row["is_default_multimodal"])
