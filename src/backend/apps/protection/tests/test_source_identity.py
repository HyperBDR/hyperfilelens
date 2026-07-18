from unittest.mock import patch

from django.test import SimpleTestCase

from apps.protection.services.source_identity import resolve_source_display_name


class SourceDisplayNameTests(SimpleTestCase):
    @patch("apps.protection.services.source_identity.Node.objects.filter")
    def test_resolves_agent_name(self, filter_nodes):
        filter_nodes.return_value.values_list.return_value.first.return_value = "zjb-2"

        name = resolve_source_display_name(
            organization_id=1,
            source_type="agent",
            source_ref_id=2,
            fallback="Backup-01-zjb-2",
        )

        self.assertEqual(name, "zjb-2")

    @patch("apps.protection.services.source_identity.SourceResource.objects.filter")
    def test_resolves_nas_name(self, filter_sources):
        filter_sources.return_value.values_list.return_value.first.return_value = "Finance NAS"

        name = resolve_source_display_name(
            organization_id=1,
            source_type="nas",
            source_ref_id=3,
            fallback="Backup-01-Finance NAS",
        )

        self.assertEqual(name, "Finance NAS")

    def test_uses_fallback_for_unknown_source_type(self):
        name = resolve_source_display_name(
            organization_id=1,
            source_type="unknown",
            source_ref_id=4,
            fallback="Configured Source",
        )

        self.assertEqual(name, "Configured Source")
