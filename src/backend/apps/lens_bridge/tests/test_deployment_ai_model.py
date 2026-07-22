from __future__ import annotations

import uuid
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase

from apps.lens_bridge.models import LensOrgLink, LensOrgModelLink
from apps.lens_bridge.services import deployment_ai_model, platform_lens, sl_client


class DeploymentAiModelConfigTests(TestCase):
    def test_requires_https_api_base(self):
        with self.assertRaises(deployment_ai_model.DeploymentAiModelConfigurationError):
            deployment_ai_model.DeploymentAiModelConfig.from_mapping(
                {
                    "provider": "openai_compatible",
                    "model_id": "model/one",
                    "display_name": "Model One",
                    "api_base": "http://models.example/v1",
                    "api_key": "secret",
                }
            )

    def test_normalizes_api_base_without_changing_path(self):
        config = deployment_ai_model.DeploymentAiModelConfig.from_mapping(
            {
                "provider": "OPENAI_COMPATIBLE",
                "model_id": "deepseek/DeepSeek-V4-Flash/8f94e",
                "display_name": "DeepSeek V4 Flash",
                "api_base": "https://models.example/custom/api/",
                "api_key": "secret",
            }
        )

        self.assertEqual(config.provider, "openai_compatible")
        self.assertEqual(config.api_base, "https://models.example/custom/api")


class DeploymentAiModelServiceTests(TestCase):
    model_uuid = uuid.UUID("876742d4-c3b7-4f6c-84a8-a3c0cc8ac38e")
    replacement_uuid = uuid.UUID("59cd45f4-ddb8-4646-839b-555b1f9f289d")

    def setUp(self):
        self.config = deployment_ai_model.DeploymentAiModelConfig(
            provider="openai_compatible",
            model_id="deepseek/DeepSeek-V4-Flash/8f94e",
            display_name="DeepSeek V4 Flash",
            api_base="https://models.example/custom/api",
            api_key="deployment-secret",
        )

    @patch("apps.lens_bridge.services.deployment_ai_model.sl_client.request_json")
    def test_first_adoption_creates_and_sets_default(self, request_json):
        request_json.side_effect = [
            {"uuid": str(self.model_uuid)},
            {"ok": True},
        ]

        result = deployment_ai_model.ensure_platform_ai_model(self.config)

        self.assertEqual(result.action, "created")
        self.assertTrue(result.connectivity_ok)
        create_payload = request_json.call_args_list[0].kwargs["json_body"]
        self.assertTrue(create_payload["is_default"])
        self.assertEqual(create_payload["config"]["api_key"], "deployment-secret")
        link = LensOrgModelLink.objects.get(
            management_key=deployment_ai_model.DEPLOYMENT_MODEL_MANAGEMENT_KEY
        )
        self.assertEqual(link.sl_config_uuid, self.model_uuid)
        self.assertEqual(link.display_name, "DeepSeek V4 Flash")
        self.assertEqual(
            LensOrgLink.objects.get(organization=link.organization).default_agent_model_ref,
            self.model_uuid,
        )

    @patch("apps.lens_bridge.services.deployment_ai_model.sl_client.request_json")
    def test_update_preserves_an_administrator_default_selection(self, request_json):
        org = platform_lens.get_or_create_platform_org()
        LensOrgModelLink.objects.create(
            organization=org,
            sl_config_uuid=self.model_uuid,
            management_key=deployment_ai_model.DEPLOYMENT_MODEL_MANAGEMENT_KEY,
        )
        other_uuid = uuid.UUID("559d6d6e-78a6-4bbf-869c-e9005033d342")
        LensOrgLink.objects.create(
            organization=org,
            default_agent_model_ref=other_uuid,
        )
        request_json.side_effect = [
            {"uuid": str(self.model_uuid), "is_default": False},
            {"uuid": str(other_uuid), "is_active": True, "is_default": True},
            {"uuid": str(self.model_uuid), "is_default": False},
            {"success": True},
        ]

        result = deployment_ai_model.ensure_platform_ai_model(self.config)

        self.assertEqual(result.action, "updated")
        update_payload = request_json.call_args_list[2].kwargs["json_body"]
        self.assertNotIn("is_default", update_payload)

    @patch("apps.lens_bridge.services.deployment_ai_model.sl_client.request_json")
    def test_missing_managed_source_lens_record_is_recreated_without_stealing_default(
        self,
        request_json,
    ):
        org = platform_lens.get_or_create_platform_org()
        link = LensOrgModelLink.objects.create(
            organization=org,
            sl_config_uuid=self.model_uuid,
            management_key=deployment_ai_model.DEPLOYMENT_MODEL_MANAGEMENT_KEY,
        )
        other_uuid = uuid.UUID("3fdd8398-aa17-4817-96b9-6d8698c99dd4")
        LensOrgLink.objects.create(
            organization=org,
            default_agent_model_ref=other_uuid,
        )
        not_found = sl_client.LensBridgeError("not found")
        not_found.status_code = 404
        request_json.side_effect = [
            not_found,
            {"uuid": str(other_uuid), "is_active": True, "is_default": True},
            {"uuid": str(self.replacement_uuid)},
            {"ok": False},
        ]

        result = deployment_ai_model.ensure_platform_ai_model(self.config)

        self.assertEqual(result.action, "recreated")
        self.assertFalse(result.connectivity_ok)
        create_payload = request_json.call_args_list[2].kwargs["json_body"]
        self.assertFalse(create_payload["is_default"])
        link.refresh_from_db()
        self.assertEqual(link.sl_config_uuid, self.replacement_uuid)

    @patch("apps.lens_bridge.services.deployment_ai_model.sl_client.request_json")
    def test_missing_managed_default_is_recreated_and_selected(self, request_json):
        org = platform_lens.get_or_create_platform_org()
        link = LensOrgModelLink.objects.create(
            organization=org,
            sl_config_uuid=self.model_uuid,
            management_key=deployment_ai_model.DEPLOYMENT_MODEL_MANAGEMENT_KEY,
        )
        defaults = LensOrgLink.objects.create(
            organization=org,
            default_agent_model_ref=self.model_uuid,
        )
        not_found = sl_client.LensBridgeError("not found")
        not_found.status_code = 404
        request_json.side_effect = [
            not_found,
            {"uuid": str(self.replacement_uuid)},
            {"ok": True},
        ]

        result = deployment_ai_model.ensure_platform_ai_model(self.config)

        self.assertEqual(result.action, "recreated")
        create_payload = request_json.call_args_list[1].kwargs["json_body"]
        self.assertTrue(create_payload["is_default"])
        defaults.refresh_from_db()
        self.assertEqual(defaults.default_agent_model_ref, self.replacement_uuid)
        link.refresh_from_db()
        self.assertEqual(link.sl_config_uuid, self.replacement_uuid)

    @patch("apps.lens_bridge.services.deployment_ai_model.sl_client.request_json")
    def test_connectivity_failure_does_not_undo_created_model(self, request_json):
        connection_error = sl_client.LensBridgeError("provider failure")
        request_json.side_effect = [
            {"uuid": str(self.model_uuid)},
            connection_error,
        ]

        result = deployment_ai_model.ensure_platform_ai_model(self.config)

        self.assertFalse(result.connectivity_ok)
        self.assertTrue(
            LensOrgModelLink.objects.filter(sl_config_uuid=self.model_uuid).exists()
        )

    @patch(
        "apps.lens_bridge.services.deployment_ai_model._persist_link",
        side_effect=DatabaseError("database unavailable"),
    )
    @patch("apps.lens_bridge.services.deployment_ai_model.sl_client.request_json")
    def test_new_source_lens_model_is_removed_when_link_persistence_fails(
        self,
        request_json,
        _persist_link,
    ):
        request_json.side_effect = [
            {"uuid": str(self.model_uuid)},
            None,
        ]

        with self.assertRaises(DatabaseError):
            deployment_ai_model.ensure_platform_ai_model(self.config)

        request_json.assert_any_call(
            "DELETE",
            f"/api/v1/admin/llm-config/{self.model_uuid}/",
        )
