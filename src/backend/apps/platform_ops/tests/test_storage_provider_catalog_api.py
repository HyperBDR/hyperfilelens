from __future__ import annotations

import copy
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.platform_ops.models import PlatformAuditLog
from apps.storage.provider_catalog.catalog import load_default_catalog
from apps.storage.provider_catalog.models import (
    StorageProviderOverride,
    StorageProviderValidationRun,
)
from apps.storage.provider_catalog.schema import (
    canonical_json_bytes,
    parse_catalog,
    provider_checksum,
)
from apps.task.models import Task


TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "provider-catalog-api",
    }
}


@override_settings(CACHES=TEST_CACHES, HFL_PLATFORM_OPS_ENABLED=True)
class StorageProviderCatalogAPITests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(
            username="provider-admin@example.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.defaults["HTTP_X_HFL_SITE_ROLE"] = "ops"
        self.client.force_authenticate(self.staff)

    def tearDown(self):
        cache.clear()

    def _content(self, provider_ids=("aliyun",), suffix=" Updated") -> str:
        catalog = copy.deepcopy(load_default_catalog())
        catalog["providers"] = [
            provider
            for provider in catalog["providers"]
            if provider["id"] in provider_ids
        ]
        for provider in catalog["providers"]:
            provider["display_name"] += suffix
        return canonical_json_bytes(catalog).decode()

    def _review(self, content: str):
        return self.client.post(
            "/api/v1/platform-ops/storage-providers/import/review",
            {"content": content},
            format="json",
        )

    def _apply(self, content: str, review: dict, **overrides):
        payload = {
            "content": content,
            "input_checksum": review["input_checksum"],
            "review_token": review["review_token"],
            "risk_confirmations": review["required_risk_confirmation_ids"],
            **overrides,
        }
        return self.client.post(
            "/api/v1/platform-ops/storage-providers/import/apply",
            payload,
            format="json",
        )

    def _create_override(self, provider_id: str, suffix=" Override"):
        provider = next(
            copy.deepcopy(item)
            for item in load_default_catalog()["providers"]
            if item["id"] == provider_id
        )
        provider["display_name"] += suffix
        return StorageProviderOverride.objects.create(
            provider_id=provider_id,
            schema_version=1,
            config=provider,
            checksum=provider_checksum(provider),
            updated_by_id=self.staff.pk,
        )

    def test_management_catalog_requires_platform_ops_staff(self):
        user = User.objects.create_user(
            username="tenant@example.com", password="Pass1234"
        )
        self.client.force_authenticate(user)

        denied = self.client.get("/api/v1/platform-ops/storage-providers")

        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.staff)
        response = self.client.get("/api/v1/platform-ops/storage-providers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["schema_version"], 1)
        self.assertEqual(response.data["providers"][0]["source"], "default")
        self.assertIsNone(response.data["providers"][0]["updated_at"])

    def test_dynamic_s3_provider_is_returned_without_static_capabilities(self):
        provider = next(
            copy.deepcopy(item)
            for item in load_default_catalog()["providers"]
            if item["id"] == "aliyun"
        )
        provider.update({"id": "tencent", "display_name": "Tencent Cloud COS"})
        provider["regions"] = [provider["regions"][0]]
        provider["regions"][0].update(
            {
                "id": "ap-shanghai",
                "external_endpoint": "cos.ap-shanghai.myqcloud.com",
                "internal_endpoint": "cos-internal.ap-shanghai.myqcloud.com",
            }
        )
        StorageProviderOverride.objects.create(
            provider_id=provider["id"],
            schema_version=1,
            config=provider,
            checksum=provider_checksum(provider),
            updated_by_id=self.staff.pk,
        )
        cache.clear()

        response = self.client.get("/api/v1/platform-ops/storage-providers")

        self.assertEqual(response.status_code, 200)
        self.assertIn("tencent", [item["id"] for item in response.data["providers"]])
        self.assertNotIn("adapter_capabilities", response.data)

    def test_validation_run_api_is_write_only_no_store_and_audited(self):
        candidate = next(
            copy.deepcopy(item)
            for item in load_default_catalog()["providers"]
            if item["id"] == "aliyun"
        )
        candidate["display_name"] += " API Validation"
        access_key = "api-test-access-key"
        secret_key = "api-test-secret-key"

        with patch(
            "apps.storage.provider_catalog.validation.current_app.send_task"
        ) as send_task:
            response = self.client.post(
                "/api/v1/platform-ops/storage-provider-validation-runs",
                {
                    "provider_id": "aliyun",
                    "region_ids": [candidate["regions"][0]["id"]],
                    "candidate_config": candidate,
                    "access_key_id": access_key,
                    "secret_access_key": secret_key,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(response["Cache-Control"], "no-store")
        serialized = json.dumps(response.data, default=str)
        self.assertNotIn(access_key, serialized)
        self.assertNotIn(secret_key, serialized)
        run = StorageProviderValidationRun.objects.get(pk=response.data["id"])
        task = Task.objects.get(pk=run.task_id)
        self.assertNotIn(access_key, json.dumps(task.request_payload))
        self.assertNotIn(secret_key, json.dumps(task.request_payload))
        self.assertEqual(send_task.call_args.kwargs["args"], [str(run.id)])

        detail = self.client.get(
            f"/api/v1/platform-ops/storage-provider-validation-runs/{run.id}"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail["Cache-Control"], "no-store")
        self.assertNotIn(access_key, json.dumps(detail.data, default=str))
        self.assertNotIn(secret_key, json.dumps(detail.data, default=str))

        audits = json.dumps(
            list(
                PlatformAuditLog.objects.filter(
                    action="storage_provider.validation.create"
                ).values("details")
            ),
            default=str,
        )
        self.assertNotIn(access_key, audits)
        self.assertNotIn(secret_key, audits)

    def test_validation_run_action_user_mismatch_returns_conflict_and_failure_audit(
        self,
    ):
        candidate = next(
            copy.deepcopy(item)
            for item in load_default_catalog()["providers"]
            if item["id"] == "aliyun"
        )
        with patch("apps.storage.provider_catalog.validation.current_app.send_task"):
            created = self.client.post(
                "/api/v1/platform-ops/storage-provider-validation-runs",
                {
                    "provider_id": "aliyun",
                    "region_ids": [candidate["regions"][0]["id"]],
                    "candidate_config": candidate,
                    "access_key_id": "owner-access",
                    "secret_access_key": "owner-secret",
                },
                format="json",
            )
        other = User.objects.create_user(
            username="other-validation-admin@example.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(other)

        response = self.client.post(
            f"/api/v1/platform-ops/storage-provider-validation-runs/{created.data['id']}/cancel",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        run = StorageProviderValidationRun.objects.get(pk=created.data["id"])
        self.assertEqual(run.status, StorageProviderValidationRun.Status.PENDING)
        audit = PlatformAuditLog.objects.filter(
            action="storage_provider.validation.cancel"
        ).get()
        self.assertEqual(audit.result, PlatformAuditLog.Result.FAILURE)

    def test_diff_is_side_effect_free_and_review_marks_validation_not_run(self):
        content = self._content(("aliyun", "huaweicloud"))

        diff = self.client.post(
            "/api/v1/platform-ops/storage-providers/import/diff",
            {"content": content},
            format="json",
        )
        review = self._review(content)

        self.assertEqual(diff.status_code, 200)
        self.assertEqual(review.status_code, 200)
        self.assertEqual(StorageProviderOverride.objects.count(), 0)
        self.assertEqual(
            [item["status"] for item in review.data["validation_evidence"]],
            ["not_run", "not_run"],
        )
        self.assertEqual(
            review.data["required_risk_confirmation_ids"],
            ["validation:not_run:aliyun", "validation:not_run:huaweicloud"],
        )

    def test_apply_requires_exact_risks_and_atomically_upserts_multiple_providers(self):
        content = self._content(("aliyun", "huaweicloud"))
        review = self._review(content).data

        missing = self._apply(content, review, risk_confirmations=[])
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(StorageProviderOverride.objects.count(), 0)

        response = self._apply(content, review)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["applied"])
        self.assertEqual(
            set(StorageProviderOverride.objects.values_list("provider_id", flat=True)),
            {"aliyun", "huaweicloud"},
        )
        self.assertTrue(
            all(
                item.updated_by_id == self.staff.pk
                for item in StorageProviderOverride.objects.all()
            )
        )

    def test_apply_detects_concurrent_provider_change_without_partial_write(self):
        content = self._content(("aliyun", "huaweicloud"))
        review = self._review(content).data
        concurrent = self._create_override("huaweicloud", " Concurrent")

        response = self._apply(content, review)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(
            StorageProviderOverride.objects.filter(provider_id="aliyun").exists()
        )
        concurrent.refresh_from_db()
        self.assertTrue(concurrent.config["display_name"].endswith(" Concurrent"))

    def test_review_token_is_bound_to_operator_and_input(self):
        content = self._content()
        review = self._review(content).data
        other = User.objects.create_user(
            username="other-provider-admin@example.com",
            password="Pass1234",
            is_staff=True,
        )
        self.client.force_authenticate(other)

        response = self._apply(content, review)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(StorageProviderOverride.objects.count(), 0)

    def test_candidate_equal_to_default_deletes_override(self):
        self._create_override("aliyun")
        catalog = copy.deepcopy(load_default_catalog())
        catalog["providers"] = [
            provider for provider in catalog["providers"] if provider["id"] == "aliyun"
        ]
        content = canonical_json_bytes(catalog).decode()
        review = self._review(content).data

        self.assertEqual(
            review["providers"][0]["persistence_action"], "delete_override"
        )
        response = self._apply(content, review)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            StorageProviderOverride.objects.filter(provider_id="aliyun").exists()
        )

    def test_export_is_deterministic_importable_selected_and_audited(self):
        response = self.client.get(
            "/api/v1/platform-ops/storage-providers/export?provider_ids=huaweicloud,aliyun"
        )

        self.assertEqual(response.status_code, 200)
        exported = json.loads(response.content)
        self.assertEqual(
            [provider["id"] for provider in exported["providers"]],
            ["huaweicloud", "aliyun"],
        )
        self.assertEqual(parse_catalog(response.content), exported)
        region = exported["providers"][0]["regions"][0]
        self.assertEqual(
            set(region),
            {
                "id",
                "display_name",
                "region_group",
                "region_group_en",
                "external_endpoint",
                "internal_endpoint",
                "driver",
                "s3_url_style",
                "use_tls",
            },
        )
        self.assertNotIn("secret", response.content.decode().lower())
        log = PlatformAuditLog.objects.get(action="storage_provider.catalog.export")
        self.assertEqual(log.details["provider_ids"], ["huaweicloud", "aliyun"])

    def test_single_reset_review_confirm_and_replay_are_idempotent(self):
        self._create_override("aliyun")
        review = self.client.post(
            "/api/v1/platform-ops/storage-providers/aliyun/reset/review",
            {},
            format="json",
        )
        self.assertEqual(review.status_code, 200)

        first = self.client.post(
            "/api/v1/platform-ops/storage-providers/aliyun/reset",
            {"reset_token": review.data["reset_token"]},
            format="json",
        )
        audit_count = PlatformAuditLog.objects.filter(
            action="storage_provider.reset"
        ).count()
        replay = self.client.post(
            "/api/v1/platform-ops/storage-providers/aliyun/reset",
            {"reset_token": review.data["reset_token"]},
            format="json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["reset"])
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.data["idempotent"])
        self.assertEqual(
            PlatformAuditLog.objects.filter(action="storage_provider.reset").count(),
            audit_count,
        )

    def test_reset_all_conflict_is_atomic(self):
        aliyun = self._create_override("aliyun")
        huaweicloud = self._create_override("huaweicloud")
        review = self.client.post(
            "/api/v1/platform-ops/storage-providers/reset/review",
            {},
            format="json",
        ).data
        huaweicloud.config = {
            **huaweicloud.config,
            "display_name": "Huawei Cloud Concurrent",
        }
        huaweicloud.checksum = provider_checksum(huaweicloud.config)
        huaweicloud.save(update_fields=["config", "checksum", "updated_at"])

        response = self.client.post(
            "/api/v1/platform-ops/storage-providers/reset",
            {"reset_token": review["reset_token"]},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(StorageProviderOverride.objects.filter(pk=aliyun.pk).exists())
        self.assertTrue(
            StorageProviderOverride.objects.filter(pk=huaweicloud.pk).exists()
        )

    def test_reset_all_review_confirm_deletes_only_reviewed_default_scope(self):
        self._create_override("aliyun")
        self._create_override("huaweicloud")
        review = self.client.post(
            "/api/v1/platform-ops/storage-providers/reset/review",
            {},
            format="json",
        ).data

        response = self.client.post(
            "/api/v1/platform-ops/storage-providers/reset",
            {"reset_token": review["reset_token"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["reset"])
        self.assertEqual(StorageProviderOverride.objects.count(), 0)
        self.assertEqual(
            response.data["provider_ids"],
            ["aliyun", "huaweicloud"],
        )

    def test_reset_token_cannot_cross_single_and_all_endpoints(self):
        self._create_override("aliyun")
        review = self.client.post(
            "/api/v1/platform-ops/storage-providers/aliyun/reset/review",
            {},
            format="json",
        ).data

        response = self.client.post(
            "/api/v1/platform-ops/storage-providers/reset",
            {"reset_token": review["reset_token"]},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(
            StorageProviderOverride.objects.filter(provider_id="aliyun").exists()
        )

    def test_apply_audit_contains_checksums_not_configuration_body(self):
        content = self._content(suffix=" UniqueAuditMarker")
        review = self._review(content).data
        response = self._apply(content, review)
        self.assertEqual(response.status_code, 200)

        log = PlatformAuditLog.objects.get(action="storage_provider.import.apply")
        serialized = json.dumps(log.details)
        self.assertNotIn("UniqueAuditMarker", serialized)
        self.assertNotIn("regions", serialized)
        self.assertIn("after_checksum", serialized)
