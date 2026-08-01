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


DIRECT_RUN_UUID = "8f5054d4-6c22-44c3-a050-dda74ad55204"


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
        side_effect=[
            {"results": [], "total": 0, "page": 1, "page_size": 100},
            {"results": [], "total": 0, "page": 1, "page_size": 100},
            {"results": [], "total": 0, "page": 1, "page_size": 100},
            {"uuid": "run-uuid", "status": "done"},
        ],
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
        objects.filter.return_value = [link]

        self.assertEqual(Command._active_run_count(), 0)
        request_json.assert_has_calls(
            [
                call(
                    "GET",
                    "/api/lens/admin/runs/",
                    params={
                        "page": 1,
                        "page_size": 100,
                        "status": "queued",
                    },
                ),
                call(
                    "GET",
                    "/api/lens/admin/runs/",
                    params={
                        "page": 1,
                        "page_size": 100,
                        "status": "running",
                    },
                ),
                call(
                    "GET",
                    "/api/lens/admin/runs/",
                    params={
                        "page": 1,
                        "page_size": 100,
                        "status": "streaming",
                    },
                ),
                call("GET", "/api/lens/admin/runs/run-uuid/"),
            ]
        )
        capture_usage.assert_called_once_with(
            link,
            {"uuid": "run-uuid", "status": "done"},
        )
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
        objects.filter.return_value = [link]

        self.assertEqual(Command._active_run_count(), 1)
        request_json.assert_called_once()

    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.sl_client.request_json",
        side_effect=[
            {"results": [], "total": 0, "page": 1, "page_size": 100},
            {"results": [], "total": 0, "page": 1, "page_size": 100},
            {"results": [], "total": 0, "page": 1, "page_size": 100},
            None,
        ],
    )
    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.LensSessionLink.objects"
    )
    def test_drain_treats_malformed_run_detail_as_active(
        self,
        objects,
        _request_json,
    ):
        link = type(
            "Link",
            (),
            {
                "active_run_uuid": DIRECT_RUN_UUID,
                "active_run_status": "running",
            },
        )()
        objects.filter.return_value = [link]

        self.assertEqual(Command._active_run_count(), 1)

    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.sl_client.request_json",
        side_effect=[
            {"results": [], "total": 0, "page": 1, "page_size": 100},
            {
                "results": [{"uuid": DIRECT_RUN_UUID, "status": "running"}],
                "total": 1,
                "page": 1,
                "page_size": 100,
            },
            {"results": [], "total": 0, "page": 1, "page_size": 100},
        ],
    )
    @patch(
        "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.LensSessionLink.objects"
    )
    def test_drain_includes_runs_created_directly_in_sourcelens(
        self,
        objects,
        _request_json,
    ):
        objects.filter.return_value = []

        self.assertEqual(Command._active_run_count(), 1)

    def test_admin_run_scan_rejects_malformed_payloads(self):
        malformed_payloads = (
            {},
            {"results": None, "total": 0},
            {"results": {}, "total": 0},
            {"results": [None], "total": 1},
            {"results": [{"uuid": "not-a-uuid", "status": "running"}], "total": 1},
            {"results": [{"uuid": DIRECT_RUN_UUID, "status": "unknown"}], "total": 1},
            {"results": [], "total": None},
            {"results": [], "total": True},
            {"results": [], "total": -1},
            {"results": [{"uuid": DIRECT_RUN_UUID, "status": "running"}], "total": 0},
            {"results": [], "total": 1},
            {"results": [{"uuid": DIRECT_RUN_UUID, "status": "running"}], "total": 101},
            {"results": [{"uuid": DIRECT_RUN_UUID, "status": "done"}], "total": 1},
        )

        for payload in malformed_payloads:
            with self.subTest(payload=payload), patch(
                "apps.lens_bridge.management.commands.sourcelens_upgrade_gate.sl_client.request_json",
                return_value=payload,
            ):
                with self.assertRaises(sl_client.LensBridgeError):
                    Command._active_admin_runs()

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
