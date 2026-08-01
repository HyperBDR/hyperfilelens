from io import StringIO
from contextlib import nullcontext
from unittest.mock import MagicMock, call, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.lens_bridge.api.views import SourceLensMaintenanceUnavailable
from apps.lens_bridge.management.commands.sourcelens_upgrade_gate import Command
from apps.lens_bridge.services import sl_client
from apps.lens_bridge.services.maintenance import (
    arm_sourcelens_maintenance,
    begin_sourcelens_maintenance,
    sourcelens_run_creation_guard,
)


class SourceLensUpgradeGateTests(SimpleTestCase):
    @patch("apps.lens_bridge.services.maintenance.begin_sourcelens_maintenance")
    @patch("apps.lens_bridge.services.maintenance._acquire_run_gate_lock")
    @patch(
        "apps.lens_bridge.services.maintenance.transaction.atomic",
        return_value=nullcontext(),
    )
    def test_maintenance_barrier_takes_exclusive_lock_before_arming(
        self, _atomic, acquire_lock, begin
    ):
        parent = MagicMock()
        parent.attach_mock(acquire_lock, "lock")
        parent.attach_mock(begin, "begin")

        arm_sourcelens_maintenance()

        self.assertEqual(
            parent.mock_calls,
            [call.lock(shared=False), call.begin()],
        )

    @patch("apps.lens_bridge.services.maintenance._acquire_run_gate_lock")
    @patch(
        "apps.lens_bridge.services.maintenance.transaction.atomic",
        return_value=nullcontext(),
    )
    def test_run_creation_guard_takes_shared_lock(self, _atomic, acquire_lock):
        with sourcelens_run_creation_guard():
            pass

        acquire_lock.assert_called_once_with(shared=True)

    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.copilot.clear_active_run"
    )
    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.usage.capture_run_usage"
    )
    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.sl_client.request_json",
        return_value={"status": "done"},
    )
    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.LensSessionLink.objects"
    )
    def test_drain_reconciles_terminal_source_lens_runs(
        self,
        objects,
        request_json,
        capture_usage,
        clear_active_run,
    ):
        link = type(
            "Link",
            (),
            {
                "active_run_uuid": "run-uuid",
                "active_run_status": "running",
                "hfl_user": object(),
            },
        )()
        objects.select_related.return_value.filter.return_value = [link]

        self.assertEqual(Command._active_run_count(), 0)
        request_json.assert_called_once_with(
            "GET",
            "/api/lens/runs/run-uuid/",
            hfl_user=link.hfl_user,
        )
        capture_usage.assert_called_once_with(link, {"status": "done"})
        clear_active_run.assert_called_once_with(link)

    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.sl_client.request_json",
        side_effect=sl_client.LensBridgeError("temporarily unavailable"),
    )
    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.LensSessionLink.objects"
    )
    def test_drain_treats_unknown_source_lens_run_as_active(
        self,
        objects,
        request_json,
    ):
        link = type(
            "Link",
            (),
            {
                "active_run_uuid": "run-uuid",
                "active_run_status": "running",
                "hfl_user": object(),
            },
        )()
        objects.select_related.return_value.filter.return_value = [link]

        self.assertEqual(Command._active_run_count(), 1)
        request_json.assert_called_once()

    @patch("apps.lens_bridge.services.maintenance.cache")
    def test_maintenance_gate_has_hard_kill_failsafe(self, cache):
        begin_sourcelens_maintenance()

        cache.set.assert_called_once_with(
            "lens_bridge:sourcelens_maintenance",
            True,
            timeout=2 * 60 * 60,
        )

    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.Command._active_run_count",
        side_effect=(1, 0),
    )
    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.arm_sourcelens_maintenance"
    )
    @patch("apps.lens_bridge.management.commands.sourcelens_upgrade_gate.time.sleep")
    def test_begin_blocks_new_runs_and_waits_for_active_runs(
        self, sleep, arm, active_count
    ):
        call_command(
            "sourcelens_upgrade_gate",
            "begin",
            timeout=5,
            stdout=StringIO(),
        )

        arm.assert_called_once_with()
        sleep.assert_called_once_with(2)
        self.assertEqual(active_count.call_count, 2)

    def test_maintenance_error_is_retryable_service_unavailable(self):
        error = SourceLensMaintenanceUnavailable()
        self.assertEqual(error.status_code, 503)
        self.assertEqual(error.get_codes(), "sourcelens_maintenance")
