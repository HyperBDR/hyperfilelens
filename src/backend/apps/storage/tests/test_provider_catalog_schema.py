from __future__ import annotations

import copy
import json
import os
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.storage.provider_catalog.catalog import load_default_catalog
from apps.storage.provider_catalog.errors import ProviderCatalogValidationError
from apps.storage.provider_catalog.schema import (
    canonical_json_bytes,
    parse_catalog,
    provider_checksum,
)


class ProviderCatalogSchemaTests(SimpleTestCase):
    def test_packaged_default_catalog_is_valid(self):
        catalog = load_default_catalog()

        self.assertEqual(catalog["schema_version"], 1)
        self.assertEqual(
            [provider["id"] for provider in catalog["providers"]],
            ["huaweicloud", "aliyun", "aws"],
        )
        self.assertNotIn("custom", [item["id"] for item in catalog["providers"]])

    def test_normalization_preserves_array_order_and_normalizes_endpoint_case(self):
        catalog = copy.deepcopy(load_default_catalog())
        provider = catalog["providers"][0]
        provider["regions"] = list(reversed(provider["regions"]))
        provider["regions"][0]["external_endpoint"] = provider["regions"][0][
            "external_endpoint"
        ].upper()
        provider["regions"][0]["internal_endpoint"] = provider["regions"][0][
            "internal_endpoint"
        ].upper()
        input_providers = list(reversed(catalog["providers"]))
        expected_regions = {
            item["id"]: [
                (region["region_group"], region["id"])
                for region in item["regions"]
            ]
            for item in input_providers
        }
        raw = json.dumps(
            {"providers": input_providers, "schema_version": 1}
        )

        normalized = parse_catalog(raw)

        self.assertEqual(
            [item["id"] for item in normalized["providers"]],
            ["aws", "aliyun", "huaweicloud"],
        )
        for item in normalized["providers"]:
            self.assertEqual(
                [(region["region_group"], region["id"]) for region in item["regions"]],
                expected_regions[item["id"]],
            )
        self.assertTrue(
            all(
                region[endpoint_field] == region[endpoint_field].lower()
                for item in normalized["providers"]
                for region in item["regions"]
                for endpoint_field in ("external_endpoint", "internal_endpoint")
            )
        )

    def test_provider_checksum_ignores_object_order_but_tracks_region_order(self):
        provider = copy.deepcopy(load_default_catalog()["providers"][0])
        reordered = {
            "regions": list(reversed(provider["regions"])),
            "enabled": provider["enabled"],
            "display_name": provider["display_name"],
            "id": provider["id"],
        }

        self.assertNotEqual(provider_checksum(provider), provider_checksum(reordered))

        reordered["regions"] = provider["regions"]
        self.assertEqual(provider_checksum(provider), provider_checksum(reordered))

    def test_canonical_json_matches_rfc8785_for_schema_value_types(self):
        self.assertEqual(
            canonical_json_bytes({"z": [True, "é"], "a": {"b": False}}),
            '{"a":{"b":false},"z":[true,"é"]}'.encode(),
        )

    def test_rejects_duplicate_json_keys_and_provider_ids(self):
        with self.assertRaises(ProviderCatalogValidationError) as duplicate_key:
            parse_catalog('{"schema_version":1,"schema_version":1,"providers":[]}')
        self.assertEqual(duplicate_key.exception.issues[0]["code"], "invalid_json")

        catalog = copy.deepcopy(load_default_catalog())
        catalog["providers"] = [catalog["providers"][0], catalog["providers"][0]]
        with self.assertRaises(ProviderCatalogValidationError) as duplicate_provider:
            parse_catalog(json.dumps(catalog))
        self.assertEqual(
            duplicate_provider.exception.issues[0]["code"], "duplicate_provider"
        )

    def test_rejects_unpaired_unicode_surrogates(self):
        with self.assertRaises(ProviderCatalogValidationError) as invalid_unicode:
            parse_catalog(
                '{"schema_version":1,"providers":[{"id":"aws","display_name":"\\ud800"}]}'
            )

        self.assertEqual(invalid_unicode.exception.issues[0]["code"], "invalid_unicode")

    def test_accepts_dynamic_provider_and_rejects_reserved_or_unsafe_values(self):
        catalog = copy.deepcopy(load_default_catalog())
        catalog["providers"][0]["secret_access_key"] = "must-not-pass"
        with self.assertRaises(ProviderCatalogValidationError):
            parse_catalog(json.dumps(catalog))

        catalog = copy.deepcopy(load_default_catalog())
        catalog["providers"] = [catalog["providers"][0]]
        catalog["providers"][0]["id"] = "tencent"
        catalog["providers"][0]["regions"][0]["external_endpoint"] = (
            "cos.ap-shanghai.myqcloud.com"
        )
        catalog["providers"][0]["regions"][0]["internal_endpoint"] = (
            "cos.ap-shanghai.myqcloud.com"
        )
        self.assertEqual(parse_catalog(json.dumps(catalog))["providers"][0]["id"], "tencent")

        catalog = copy.deepcopy(load_default_catalog())
        catalog["providers"] = [catalog["providers"][0]]
        catalog["providers"][0]["id"] = "custom"
        with self.assertRaises(ProviderCatalogValidationError) as reserved:
            parse_catalog(json.dumps(catalog))
        self.assertEqual(
            reserved.exception.issues[0]["code"], "reserved_provider"
        )

        catalog = copy.deepcopy(load_default_catalog())
        catalog["providers"] = [catalog["providers"][0]]
        catalog["providers"][0]["regions"][0]["external_endpoint"] = (
            "127.0.0.1"
        )
        with self.assertRaises(ProviderCatalogValidationError) as endpoint:
            parse_catalog(json.dumps(catalog))
        self.assertEqual(endpoint.exception.issues[0]["code"], "invalid_endpoint")

    def test_applies_byte_depth_provider_and_region_limits_before_use(self):
        with patch.dict(
            os.environ,
            {"STORAGE_PROVIDER_CATALOG_MAX_BYTES": "8"},
        ):
            with self.assertRaises(ProviderCatalogValidationError) as too_large:
                parse_catalog('{"schema_version":1,"providers":[]}')
        self.assertEqual(too_large.exception.issues[0]["code"], "resource_limit")

        with patch.dict(
            os.environ,
            {"STORAGE_PROVIDER_CATALOG_MAX_DEPTH": "1"},
        ):
            with self.assertRaises(ProviderCatalogValidationError) as too_deep:
                parse_catalog('{"schema_version":1,"providers":[]}')
        self.assertEqual(too_deep.exception.issues[0]["code"], "resource_limit")

        catalog = copy.deepcopy(load_default_catalog())
        with patch.dict(
            os.environ,
            {"STORAGE_PROVIDER_CATALOG_MAX_PROVIDERS": "1"},
        ):
            with self.assertRaises(ProviderCatalogValidationError):
                parse_catalog(json.dumps(catalog))

        catalog["providers"] = [catalog["providers"][0]]
        with patch.dict(
            os.environ,
            {"STORAGE_PROVIDER_CATALOG_MAX_REGIONS": "2"},
        ):
            with self.assertRaises(ProviderCatalogValidationError):
                parse_catalog(json.dumps(catalog))
