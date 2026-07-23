from django.test import TestCase, override_settings

from apps.platform_ops.models import PlatformRuntimeSetting
from apps.platform_ops.services.internal.runtime_settings import (
    KEY_IDENTITY_PLATFORM_OPS,
    platform_ops_enabled,
)


@override_settings(HFL_PLATFORM_OPS_ENABLED=True)
class RuntimeSettingsConsistencyTests(TestCase):
    def test_external_database_update_is_visible_without_local_invalidation(self):
        setting = PlatformRuntimeSetting.objects.create(
            key=KEY_IDENTITY_PLATFORM_OPS,
            value_text="false",
        )
        self.assertFalse(platform_ops_enabled())

        PlatformRuntimeSetting.objects.filter(pk=setting.pk).update(value_text="true")

        self.assertTrue(platform_ops_enabled())
