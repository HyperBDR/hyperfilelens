from __future__ import annotations

import copy
import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.storage.provider_catalog.catalog import (
    default_provider_records,
    effective_provider_records,
)
from apps.storage.provider_catalog.models import StorageProviderOverride
from apps.storage.provider_catalog.schema import provider_checksum


TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "provider-catalog-selectors",
    }
}


@override_settings(CACHES=TEST_CACHES)
class ProviderCatalogSelectorTests(TransactionTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _override(self, provider_id: str, display_name: str) -> StorageProviderOverride:
        provider = copy.deepcopy(default_provider_records()[provider_id]["config"])
        provider["display_name"] = display_name
        return StorageProviderOverride.objects.create(
            provider_id=provider_id,
            schema_version=1,
            config=provider,
            checksum=provider_checksum(provider),
        )

    def test_defaults_are_not_materialized_in_database(self):
        records = effective_provider_records()

        self.assertEqual(StorageProviderOverride.objects.count(), 0)
        self.assertTrue(all(item["source"] == "default" for item in records.values()))
        self.assertTrue(all(item["updated_at"] is None for item in records.values()))

    def test_override_replaces_only_the_matching_provider(self):
        self._override("aliyun", "Alibaba Cloud OSS Enterprise")

        records = effective_provider_records()

        self.assertEqual(records["aliyun"]["source"], "override")
        self.assertEqual(
            records["aliyun"]["config"]["display_name"],
            "Alibaba Cloud OSS Enterprise",
        )
        self.assertEqual(records["huaweicloud"]["source"], "default")
        self.assertIsNotNone(records["aliyun"]["updated_at"])

    def test_committed_override_is_visible_without_cache_invalidation(self):
        self._override("huaweicloud", "Huawei Cloud OBS Updated")

        self.assertEqual(
            effective_provider_records()["huaweicloud"]["config"]["display_name"],
            "Huawei Cloud OBS Updated",
        )

    def test_corrupt_override_fails_closed_instead_of_falling_back(self):
        provider = copy.deepcopy(default_provider_records()["aliyun"]["config"])
        StorageProviderOverride.objects.create(
            provider_id="aliyun",
            schema_version=1,
            config=provider,
            checksum="0" * 64,
        )

        with self.assertRaises(ImproperlyConfigured):
            effective_provider_records()

    def test_database_enforces_config_identity_and_timestamp_default(self):
        provider = copy.deepcopy(default_provider_records()["aliyun"]["config"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            StorageProviderOverride.objects.create(
                provider_id="huaweicloud",
                schema_version=1,
                config=provider,
                checksum=provider_checksum(provider),
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO storage_provider_override "
                "(provider_id, schema_version, config, checksum) "
                "VALUES (%s, %s, %s::jsonb, %s) RETURNING updated_at",
                ["aliyun", 1, json.dumps(provider), provider_checksum(provider)],
            )
            updated_at = cursor.fetchone()[0]
        self.assertIsNotNone(updated_at)


@override_settings(CACHES=TEST_CACHES)
class ProviderCatalogReadAPITests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="catalog-reader@example.com",
            password="Pass1234",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def tearDown(self):
        cache.clear()

    def test_authenticated_repository_page_can_read_effective_catalog(self):
        response = self.client.get("/api/v1/storage/provider-catalog/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["schema_version"], 1)
        self.assertEqual(
            [provider["id"] for provider in response.data["providers"]],
            ["huaweicloud", "aliyun"],
        )
        self.assertNotIn("source", response.data["providers"][0])
        self.assertNotIn("checksum", response.data["providers"][0])

    def test_anonymous_repository_page_catalog_read_is_denied(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/storage/provider-catalog/")

        self.assertIn(response.status_code, (401, 403))
