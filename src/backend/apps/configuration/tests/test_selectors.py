"""Tests for configuration resolution and cache invalidation."""

from django.core.cache import cache
from django.test import TestCase

from apps.configuration.constants import CACHE_VERSION_KEY
from apps.configuration.models import GlobalConfig
from apps.configuration.selectors.interface import get_config
from apps.configuration.selectors.internal.cache import bump_cache_version


class GetConfigCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        cache.set(CACHE_VERSION_KEY, 1, timeout=None)

    def test_tenant_miss_uses_global_without_tenant_cache_pollution(self):
        GlobalConfig.objects.create(
            key="test.feature",
            scope=GlobalConfig.Scope.GLOBAL,
            tenant_key="",
            value_type=GlobalConfig.ValueType.NUMBER,
            value=7,
        )

        first = get_config("test.feature", tenant_key="acme", use_cache=True)
        self.assertEqual(first, 7)

        GlobalConfig.objects.filter(
            key="test.feature",
            scope=GlobalConfig.Scope.GLOBAL,
        ).update(
            value=14,
        )
        bump_cache_version()

        second = get_config("test.feature", tenant_key="acme", use_cache=True)
        self.assertEqual(second, 14)

    def test_defaults_are_not_cached(self):
        GlobalConfig.objects.filter(key="test.missing").delete()
        value = get_config("test.missing", default=99, use_cache=True)
        self.assertEqual(value, 99)

        GlobalConfig.objects.create(
            key="test.missing",
            scope=GlobalConfig.Scope.GLOBAL,
            tenant_key="",
            value_type=GlobalConfig.ValueType.NUMBER,
            value=1,
        )
        bump_cache_version()

        updated = get_config("test.missing", default=99, use_cache=True)
        self.assertEqual(updated, 1)
