from django.test import SimpleTestCase

from apps.protection.models import FileFilterRule
from apps.protection.services import file_filter_summary
from apps.protection.services.file_filter_runtime import file_filter_agent_payload


class FileFilterRuntimeTests(SimpleTestCase):
    def test_file_filter_agent_payload_maps_all_fields(self):
        rule = FileFilterRule(
            name="Production filters",
            ignore_patterns="*.tmp\n**/node_modules/**",
            large_file_limit_enabled=True,
            large_file_bytes_max=524288000,
            ignore_cache_directories=True,
            current_filesystem_only=False,
        )

        payload = file_filter_agent_payload(rule)
        assert payload is not None
        self.assertEqual(payload["ignore_patterns"], ["*.tmp", "**/node_modules/**"])
        self.assertEqual(payload["large_file_bytes_max"], 524288000)
        self.assertTrue(payload["active"])
        self.assertTrue(payload["configured"])
        self.assertTrue(payload["ignore_cache_directories"])

    def test_file_filter_agent_payload_disables_all_fields_without_rule(self):
        payload = file_filter_agent_payload(None)
        self.assertIsNone(payload["rule_id"])
        self.assertFalse(payload["active"])
        self.assertFalse(payload["configured"])

    def test_file_filter_agent_payload_disables_all_fields_for_inactive_rule(self):
        rule = FileFilterRule(
            id=42,
            name="Disabled filters",
            is_active=False,
            ignore_patterns="*.tmp",
        )

        payload = file_filter_agent_payload(rule)
        self.assertEqual(payload["rule_id"], 42)
        self.assertFalse(payload["active"])
        self.assertFalse(payload["configured"])

    def test_file_filter_agent_payload_clears_stale_size_when_limit_is_disabled(self):
        rule = FileFilterRule(
            name="Disabled size limit",
            large_file_limit_enabled=False,
            large_file_bytes_max=524288000,
        )

        payload = file_filter_agent_payload(rule)

        self.assertEqual(payload["large_file_bytes_max"], 0)

    def test_file_filter_summary_separates_exception_patterns(self):
        rule = FileFilterRule(
            name="Production filters",
            ignore_patterns="*.tmp\n!important.tmp\n**/cache/**",
        )

        summary = file_filter_summary(rule)

        self.assertIn("Exclude: *.tmp", summary)
        self.assertIn("cache/", summary)
        self.assertIn("Exceptions: important.tmp", summary)
