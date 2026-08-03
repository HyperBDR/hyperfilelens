import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.iam.models import Organization
from apps.lens_bridge.models import LensGatewayLink, LensSessionLink
from apps.lens_bridge.services.sync_queue import (
    queue_copilot_chat_provision,
    queue_copilot_chat_teardown,
)
from apps.lens_bridge.services import chat_lifecycle
from apps.lens_bridge.tasks import chat_lifecycle as chat_lifecycle_tasks
from apps.node.models import Node
from apps.protection.models import (
    BackupConfig,
    BackupSourceSnapshot,
    BackupSourceSnapshotDirectory,
)


class CopilotLifecycleQueueTests(SimpleTestCase):
    @patch(
        "apps.lens_bridge.services.chat_lifecycle.run_copilot_chat_provision",
        return_value={"session_link_id": 42, "status": "waiting"},
    )
    def test_pending_task_schedules_a_short_follow_up(self, _run):
        task = chat_lifecycle_tasks.execute_copilot_chat_provision_task
        with patch.object(task, "apply_async") as apply_async:
            result = task.run(session_link_id=42)

        self.assertEqual(result["status"], "waiting")
        apply_async.assert_called_once_with(
            kwargs={"session_link_id": 42},
            countdown=5,
        )

    @patch("apps.lens_bridge.services.chat_lifecycle._release_provision_claim")
    @patch(
        "apps.lens_bridge.services.chat_lifecycle._claim_copilot_chat_provision",
        return_value=("claim-token", "claimed"),
    )
    @patch(
        "apps.lens_bridge.services.chat_lifecycle._run_copilot_chat_provision",
        return_value={"session_link_id": 42, "status": "waiting"},
    )
    def test_pending_conversion_releases_provision_worker_lease(
        self,
        _run,
        _claim,
        release_claim,
    ):
        result = chat_lifecycle.run_copilot_chat_provision(
            session_link_id=42
        )

        self.assertEqual(result["status"], "waiting")
        release_claim.assert_called_once_with(42, "claim-token")

    @patch("apps.lens_bridge.services.chat_lifecycle.LensSessionLink.objects.filter")
    @patch("apps.lens_bridge.services.chat_lifecycle._mark_provision_failed_by_id")
    @patch(
        "apps.lens_bridge.services.chat_lifecycle._claim_copilot_chat_provision",
        return_value=("claim-token", "claimed"),
    )
    @patch(
        "apps.lens_bridge.services.chat_lifecycle._run_copilot_chat_provision",
        side_effect=RuntimeError("database schema mismatch"),
    )
    def test_provision_records_failures_before_pipeline_starts(
        self,
        _run,
        _claim,
        mark_failed,
        filter_sessions,
    ):
        filter_sessions.return_value.first.return_value = None
        with self.assertRaisesRegex(RuntimeError, "database schema mismatch"):
            chat_lifecycle.run_copilot_chat_provision(session_link_id=42)

        mark_failed.assert_called_once_with(
            42,
            "claim-token",
            "database schema mismatch",
        )

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
    def test_unclaimed_provisioning_session_retry_is_requeued(self, queue_provision):
        session = self.create_session(LensSessionLink.LifecycleStatus.PROVISIONING)

        with self.captureOnCommitCallbacks(execute=True):
            updated = chat_lifecycle.retry_copilot_chat_provision(session)

        self.assertEqual(updated.lifecycle_status, LensSessionLink.LifecycleStatus.PROVISIONING)
        queue_provision.assert_called_once_with(session.id)

    @patch("apps.lens_bridge.services.chat_lifecycle._queue_provision_or_mark_failed")
    def test_live_provisioning_session_retry_is_idempotent(self, queue_provision):
        session = self.create_session(LensSessionLink.LifecycleStatus.PROVISIONING)
        session.provision_claim_token = uuid.uuid4()
        session.provision_claimed_at = timezone.now()
        session.provision_next_retry_at = timezone.now() + timedelta(minutes=1)
        session.save(
            update_fields=[
                "provision_claim_token",
                "provision_claimed_at",
                "provision_next_retry_at",
                "updated_at",
            ]
        )

        updated = chat_lifecycle.retry_copilot_chat_provision(session)

        self.assertEqual(
            updated.lifecycle_status,
            LensSessionLink.LifecycleStatus.PROVISIONING,
        )
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


class CopilotChatModelBindingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            key="copilot-model-binding",
            name="Copilot Model Binding",
        )
        self.user = get_user_model().objects.create_user(
            username="copilot-model-binding@example.test",
            email="copilot-model-binding@example.test",
        )
        self.gateway = Node.objects.create(
            organization=self.organization,
            name="private-gateway",
            role=Node.Role.GATEWAY,
        )
        self.gateway_link = LensGatewayLink.objects.create(
            organization=self.organization,
            gateway=self.gateway,
            owner_user=self.user,
            scope=LensGatewayLink.GatewayScope.USER,
            origin=LensGatewayLink.Origin.USER,
        )
        self.config = BackupConfig.objects.create(
            organization_id=self.organization.id,
            name="Documents",
            source_type="host",
            source_ref_id=1,
            repository_id=1,
        )
        self.snapshot = BackupSourceSnapshot.objects.create(
            organization_id=self.organization.id,
            snapshot_uid="snapshot-model-binding",
            idempotency_key="snapshot-model-binding",
            source_type="host",
            source_ref_id=1,
            backup_config_id=self.config.id,
            repository_id=1,
            task_id=1,
            status=BackupSourceSnapshot.Status.AVAILABLE,
        )
        self.directory = BackupSourceSnapshotDirectory.objects.create(
            source_snapshot=self.snapshot,
            organization_id=self.organization.id,
            backup_config_id=self.config.id,
            backup_config_dir_id=1,
            source_path="/documents",
            repository_id=1,
            status=BackupSourceSnapshotDirectory.Status.AVAILABLE,
        )

    def _create_chat(self):
        return chat_lifecycle.create_copilot_chat(
            self.organization,
            user=self.user,
            backup_config_id=self.config.id,
            backup_source_snapshot_id=self.snapshot.id,
            source_scopes=[
                {
                    "source_path": "/documents",
                    "backup_snapshot_directory_id": self.directory.id,
                    "path_type": "dir",
                }
            ],
            gateway_mode=LensSessionLink.GatewaySelectionMode.MANUAL,
            gateway_link_id=self.gateway_link.id,
        )

    @patch(
        "apps.lens_bridge.services.chat_lifecycle."
        "provisioning.default_model_refs_for_org",
        return_value=(None, None),
    )
    @patch(
        "apps.lens_bridge.services.chat_lifecycle."
        "platform_lens.resolve_gateway_link_for_copilot"
    )
    @patch(
        "apps.lens_bridge.services.gateway_execution."
        "context_for_gateway_link"
    )
    def test_missing_agent_model_blocks_chat_creation(
        self,
        _context,
        resolve_gateway,
        _default_models,
    ):
        resolve_gateway.return_value = self.gateway_link

        with self.assertRaises(ValidationError):
            self._create_chat()

        self.assertFalse(
            LensSessionLink.objects.filter(
                organization=self.organization
            ).exists()
        )

    @patch(
        "apps.lens_bridge.services.chat_lifecycle."
        "_queue_provision_or_mark_failed"
    )
    @patch(
        "apps.lens_bridge.services.chat_lifecycle."
        "provisioning.default_model_refs_for_org"
    )
    @patch(
        "apps.lens_bridge.services.chat_lifecycle."
        "platform_lens.resolve_gateway_link_for_copilot"
    )
    @patch(
        "apps.lens_bridge.services.gateway_execution."
        "context_for_gateway_link"
    )
    def test_missing_multimodal_model_keeps_text_chat_available(
        self,
        _context,
        resolve_gateway,
        default_models,
        queue_provision,
    ):
        agent_uuid = uuid.uuid4()
        resolve_gateway.return_value = self.gateway_link
        default_models.return_value = (str(agent_uuid), None)

        with self.captureOnCommitCallbacks(execute=True):
            session = self._create_chat()

        self.assertEqual(str(session.agent_model_ref), str(agent_uuid))
        self.assertIsNone(session.multimodal_model_ref)
        queue_provision.assert_called_once_with(session.id)
