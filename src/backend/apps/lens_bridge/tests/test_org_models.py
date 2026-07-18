from unittest.mock import patch

from django.test import SimpleTestCase

from apps.lens_bridge.services import org_models


class ActiveLlmConfigsTests(SimpleTestCase):
    @patch("apps.lens_bridge.services.org_models.list_all_llm_configs")
    def test_returns_platform_models_that_are_active(self, list_configs):
        list_configs.return_value = [
            {"uuid": "first", "is_active": True},
            {"uuid": "inactive", "is_active": False},
            {"uuid": "disabled", "status": "disabled"},
            {"uuid": "second"},
        ]

        rows = org_models.active_llm_configs(org=object())

        self.assertEqual([row["uuid"] for row in rows], ["first", "second"])
