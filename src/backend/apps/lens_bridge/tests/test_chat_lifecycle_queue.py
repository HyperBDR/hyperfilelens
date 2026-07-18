from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import LensSessionLink
from apps.lens_bridge.services.sync_queue import (
    queue_copilot_chat_provision,
    queue_copilot_chat_teardown,
)
from apps.lens_bridge.services import chat_lifecycle


class CopilotLifecycleQueueTests(SimpleTestCase):
    @patch("apps.lens_bridge.services.chat_lifecycle._mark_provision_failed_by_id")
    @patch(
        "apps.lens_bridge.services.chat_lifecycle._run_copilot_chat_provision",
        side_effect=RuntimeError("database schema mismatch"),
    )
    def test_provision_records_failures_before_pipeline_starts(self, _run, mark_failed):
        with self.assertRaisesRegex(RuntimeError, "database schema mismatch"):
            chat_lifecycle.run_copilot_chat_provision(session_link_id=42)

        mark_failed.assert_called_once_with(42, "database schema mismatch")

    @patch("apps.lens_bridge.tasks.chat_lifecycle.execute_copilot_chat_provision_task.delay")
    def test_provision_dispatches_to_celery(self, delay):
        queue_copilot_chat_provision(session_link_id=42)

        delay.assert_called_once_with(session_link_id=42)

    @patch(
        "apps.lens_bridge.tasks.chat_lifecycle.execute_copilot_chat_teardown_task.delay",
        side_effect=ConnectionError("broker unavailable"),
    )
    def test_teardown_queue_failure_does_not_use_daemon_thread(self, _delay):
        with self.assertRaisesRegex(RuntimeError, "Unable to queue chat teardown"):
            queue_copilot_chat_teardown(session_link_id=42)


class CopilotDefaultTitleTests(SimpleTestCase):
    def test_extracts_windows_directory_name(self):
        self.assertEqual(
            chat_lifecycle._source_path_basename(r"C:\Finance\Reports"),
            "Reports",
        )

    def test_extracts_posix_file_name(self):
        self.assertEqual(
            chat_lifecycle._source_path_basename("/srv/contracts/report.pdf"),
            "report.pdf",
        )

    def test_drive_root_uses_source_fallback(self):
        self.assertEqual(chat_lifecycle._source_path_basename("C:\\"), "")

    @patch(
        "apps.lens_bridge.services.chat_lifecycle._unique_session_title",
        side_effect=lambda _org, *, user, base_title: base_title,
    )
    def test_multiple_scopes_use_first_item_and_remaining_count(self, _unique_title):
        title = chat_lifecycle._default_session_title(
            object(),
            user=object(),
            source_name="zjb-2",
            source_scopes=[
                {"source_path": r"C:\Finance\Reports"},
                {"source_path": r"C:\Finance\Contracts"},
                {"source_path": r"C:\Finance\Forecasts"},
            ],
        )

        self.assertEqual(title, "Reports +2")

    @patch("apps.lens_bridge.services.chat_lifecycle.LensSessionLink.objects.filter")
    def test_duplicate_titles_use_parenthesized_number(self, filter_sessions):
        filter_sessions.return_value.values_list.return_value = ["Reports", "Reports (2)"]

        title = chat_lifecycle._unique_session_title(
            object(),
            user=object(),
            base_title="Reports",
        )

        self.assertEqual(title, "Reports (3)")


class CopilotRetryTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(key="copilot-retry", name="Copilot Retry")
        self.user = get_user_model().objects.create_user(
            username="copilot-retry",
            email="copilot-retry@example.com",
            password="test-password",
        )

    def create_session(self, lifecycle_status: str) -> LensSessionLink:
        return LensSessionLink.objects.create(
            organization=self.organization,
            hfl_user=self.user,
            title="Retry Chat",
            lifecycle_status=lifecycle_status,
        )

    @patch("apps.lens_bridge.services.chat_lifecycle._queue_provision_or_mark_failed")
    def test_failed_session_is_queued_once(self, queue_provision):
        session = self.create_session(LensSessionLink.LifecycleStatus.FAILED)

        with self.captureOnCommitCallbacks(execute=True):
            updated = chat_lifecycle.retry_copilot_chat_provision(session)

        self.assertEqual(updated.lifecycle_status, LensSessionLink.LifecycleStatus.PROVISIONING)
        self.assertEqual(updated.provision_phase, LensSessionLink.ProvisionPhase.QUEUED)
        queue_provision.assert_called_once_with(session.id)

    @patch("apps.lens_bridge.services.chat_lifecycle._queue_provision_or_mark_failed")
    def test_provisioning_session_retry_is_idempotent(self, queue_provision):
        session = self.create_session(LensSessionLink.LifecycleStatus.PROVISIONING)

        updated = chat_lifecycle.retry_copilot_chat_provision(session)

        self.assertEqual(updated.lifecycle_status, LensSessionLink.LifecycleStatus.PROVISIONING)
        queue_provision.assert_not_called()

    @patch("apps.lens_bridge.services.chat_lifecycle._queue_provision_or_mark_failed")
    def test_ready_session_retry_returns_current_state(self, queue_provision):
        session = self.create_session(LensSessionLink.LifecycleStatus.READY)

        updated = chat_lifecycle.retry_copilot_chat_provision(session)

        self.assertEqual(updated.lifecycle_status, LensSessionLink.LifecycleStatus.READY)
        queue_provision.assert_not_called()

    def test_deleting_session_is_not_retryable(self):
        session = self.create_session(LensSessionLink.LifecycleStatus.DELETING)

        with self.assertRaisesRegex(ValidationError, "Session is not retryable"):
            chat_lifecycle.retry_copilot_chat_provision(session)
