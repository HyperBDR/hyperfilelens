from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.lens_bridge.api.serializers import (
    LensIngestPolicyInputSerializer,
    LensKnowledgeSourceUpdateSerializer,
)
from apps.lens_bridge.models import LensKnowledgeSource
from apps.lens_bridge.services import ingest_policy


class ManagedRestoreIngestPolicyTests(SimpleTestCase):
    @patch(
        "apps.lens_bridge.services.ingest_policy."
        "provisioning.default_multimodal_model_ref_for_org",
        return_value=None,
    )
    def test_text_conversion_stays_enabled_without_multimodal_model(
        self,
        _default_multimodal,
    ):
        policy = ingest_policy.managed_restore_default_policy(object())

        self.assertTrue(policy["document"])
        self.assertFalse(policy["image"])
        self.assertFalse(policy["embedded_image"])
        self.assertFalse(policy["pdf_render_scanned_pages"])
        self.assertIsNone(policy["vision_model_ref"])
        self.assertIsNone(policy["document_model_ref"])

    @patch(
        "apps.lens_bridge.services.ingest_policy."
        "provisioning.default_multimodal_model_ref_for_org"
    )
    def test_multimodal_default_enables_visual_conversion(
        self,
        default_multimodal,
    ):
        multimodal_ref = "f658a5ed-8878-4c81-8428-87a3926203ab"
        default_multimodal.return_value = multimodal_ref

        policy = ingest_policy.managed_restore_default_policy(object())

        self.assertTrue(policy["document"])
        self.assertTrue(policy["image"])
        self.assertTrue(policy["embedded_image"])
        self.assertTrue(policy["pdf_render_scanned_pages"])
        self.assertEqual(policy["vision_model_ref"], multimodal_ref)
        self.assertIsNone(policy["document_model_ref"])

    @patch(
        "apps.lens_bridge.services.ingest_policy."
        "provisioning.default_multimodal_model_ref_for_org"
    )
    def test_user_model_references_are_replaced_by_admin_default(
        self,
        default_multimodal,
    ):
        default_multimodal.return_value = "admin-model"

        policy = ingest_policy.policy_from_user_input(
            {
                "image": True,
                "vision_model_ref": "another-organization-model",
                "document_model_ref": "untrusted-document-model",
            },
            object(),
        )

        self.assertEqual(policy["vision_model_ref"], "admin-model")
        self.assertIsNone(policy["document_model_ref"])

    def test_persisted_string_boolean_is_not_truthy(self):
        policy = ingest_policy.normalize_ingest_policy(
            {"document": "false", "image": "true"}
        )

        self.assertFalse(policy["document"])
        self.assertFalse(policy["image"])

    def test_persisted_limits_are_capped(self):
        policy = ingest_policy.normalize_ingest_policy(
            {"max_file_size_mb": 10_000, "pdf_render_dpi": 5000}
        )

        self.assertEqual(policy["max_file_size_mb"], 256)
        self.assertEqual(policy["pdf_render_dpi"], 300)

    def test_api_rejects_tenant_model_override(self):
        serializer = LensIngestPolicyInputSerializer(
            data={"image": True, "vision_model_ref": "foreign-model"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("vision_model_ref", serializer.errors)

    def test_api_rejects_excessive_resource_limit(self):
        serializer = LensIngestPolicyInputSerializer(
            data={"document": True, "max_file_size_mb": 10_000}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("max_file_size_mb", serializer.errors)

    def test_api_rejects_policy_change_during_active_sync(self):
        knowledge_source = MagicMock(
            status=LensKnowledgeSource.Status.SYNCING,
            ingest_policy_json={"document": True},
        )
        serializer = LensKnowledgeSourceUpdateSerializer(
            knowledge_source,
            data={"ingest_policy": {"image": True}},
            partial=True,
            context={"org": object()},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("ingest_policy", serializer.errors)

    @patch(
        "apps.lens_bridge.services.ingest_policy."
        "provisioning.default_multimodal_model_ref_for_org",
        return_value="admin-vision-model",
    )
    def test_partial_policy_update_is_merged_with_persisted_policy(
        self,
        _default_multimodal,
    ):
        knowledge_source = MagicMock(
            status=LensKnowledgeSource.Status.READY,
            linked_version_mode=LensKnowledgeSource.LinkedVersionMode.LATEST,
            ingest_policy_json={"document": True},
        )
        serializer = LensKnowledgeSourceUpdateSerializer(
            knowledge_source,
            data={"ingest_policy": {"embedded_image": True}},
            partial=True,
            context={"org": object()},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        policy = serializer.validated_data["ingest_policy_json"]
        self.assertTrue(policy["document"])
        self.assertTrue(policy["embedded_image"])
        self.assertEqual(policy["vision_model_ref"], "admin-vision-model")
