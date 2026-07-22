from __future__ import annotations

import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.lens_bridge.models import LensOrgLink, LensOrgModelLink
from apps.lens_bridge.services import deployment_ai_model, platform_lens


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class PlatformOpsLensModelTests(TestCase):
    model_uuid = uuid.UUID("68c7f764-561c-475a-9cc4-50f6f9457b5c")
    path = f"/api/v1/platform-ops/lens/models/{model_uuid}"

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="model-admin@example.com",
            email="model-admin@example.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff)
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        self.link = LensOrgModelLink.objects.create(
            organization=platform_lens.get_or_create_platform_org(),
            sl_config_uuid=self.model_uuid,
            display_name="Deployment Model",
            management_key=deployment_ai_model.DEPLOYMENT_MODEL_MANAGEMENT_KEY,
        )

    @patch("apps.platform_ops.api.views.lens.sl_client.request_json")
    def test_detail_marks_deployment_managed_model(self, request_json):
        request_json.return_value = {
            "uuid": str(self.model_uuid),
            "provider": "openai_compatible",
            "config": {"model": "model/one", "api_key": "********"},
            "is_active": True,
            "is_default": True,
        }

        response = self.client.get(self.path)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["deployment_managed"])
        self.assertTrue(response.data["is_default"])
        self.assertEqual(response.data["name"], "Deployment Model")

    @patch("apps.platform_ops.api.views.lens.sl_client.request_json")
    def test_connection_fields_are_read_only(self, request_json):
        response = self.client.patch(
            self.path,
            {"config": {"model": "other"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "AI_MODEL_MANAGED_BY_DEPLOYMENT")
        request_json.assert_not_called()

    @patch("apps.platform_ops.api.views.lens.sl_client.request_json")
    def test_managed_model_can_be_selected_as_default(self, request_json):
        request_json.return_value = {
            "uuid": str(self.model_uuid),
            "provider": "openai_compatible",
            "config": {"model": "model/one"},
            "is_active": True,
            "is_default": True,
        }

        response = self.client.patch(
            self.path,
            {"is_default": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_default"])
        self.assertEqual(
            LensOrgLink.objects.get(
                organization=self.link.organization
            ).default_agent_model_ref,
            self.model_uuid,
        )
        request_json.assert_called_once_with(
            "PUT",
            f"/api/v1/admin/llm-config/{self.model_uuid}/",
            json_body={"is_default": True},
        )

    @patch("apps.platform_ops.api.views.lens.sl_client.request_json")
    def test_managed_model_cannot_be_deleted(self, request_json):
        response = self.client.delete(self.path)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        request_json.assert_not_called()

    @patch("apps.platform_ops.api.views.lens.sl_client.request_json")
    def test_managed_model_connection_test_remains_available(self, request_json):
        request_json.return_value = {"ok": True}

        response = self.client.post(f"{self.path}/test-call", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        request_json.assert_called_once_with(
            "POST",
            f"/api/v1/admin/llm-config/{self.model_uuid}/test-call/",
            json_body={},
        )
