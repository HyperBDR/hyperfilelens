from unittest.mock import MagicMock, patch
from uuid import UUID

from django.test import SimpleTestCase

from apps.lens_bridge.services import assistant_access, assistants


class SoftDeleteAssistantLinkTests(SimpleTestCase):
    @patch("apps.lens_bridge.services.assistant_access.LensAssistantLink")
    def test_soft_deletes_existing_link(self, mock_model):
        link = MagicMock(is_deleted=False)
        mock_model.all_objects.filter.return_value.first.return_value = link

        assistant_access.soft_delete_assistant_link(
            MagicMock(),
            UUID("11111111-1111-1111-1111-111111111111"),
        )

        link.soft_delete.assert_called_once()

    @patch("apps.lens_bridge.services.assistant_access.LensAssistantLink")
    def test_creates_tombstone_when_link_missing(self, mock_model):
        mock_model.all_objects.filter.return_value.first.return_value = None

        assistant_access.soft_delete_assistant_link(
            MagicMock(),
            UUID("11111111-1111-1111-1111-111111111111"),
        )

        mock_model.all_objects.create.assert_called_once()
        kwargs = mock_model.all_objects.create.call_args.kwargs
        self.assertTrue(kwargs["is_deleted"])


class DeleteOrgAssistantKsReassignTests(SimpleTestCase):
    @patch("apps.lens_bridge.services.assistants._delete_sl_assistant")
    @patch("apps.lens_bridge.services.assistants._reassign_ks_primary_assistant")
    @patch("apps.lens_bridge.services.assistants.LensKnowledgeSource")
    @patch("apps.lens_bridge.services.assistants.assistant_access")
    @patch("apps.lens_bridge.services.assistants.get_org_assistant")
    def test_reassigns_ks_when_primary_assistant_deleted(
        self,
        mock_get,
        mock_access,
        mock_ks_model,
        mock_reassign,
        mock_delete,
    ):
        deleted = UUID("22222222-2222-2222-2222-222222222222")
        mock_ks_model.objects.filter.return_value.values_list.return_value = [7, 8]
        org = MagicMock()

        assistants.delete_org_assistant(org, deleted)

        mock_delete.assert_called_once_with(deleted)
        mock_access.soft_delete_assistant_link.assert_called_once_with(org, deleted)
        mock_ks_model.objects.filter.return_value.update.assert_called_once_with(
            sl_assistant_uuid=None,
        )
        mock_reassign.assert_any_call(org, 7)
        mock_reassign.assert_any_call(org, 8)
        self.assertEqual(mock_reassign.call_count, 2)
