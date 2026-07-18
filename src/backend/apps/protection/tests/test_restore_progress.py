from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.protection.services.progress.restore_runtime import _lane_from_item
from apps.restore.models import RestoreRecordItem


class RestoreProgressLaneTests(SimpleTestCase):
    def test_snapshot_size_is_authoritative_not_reference(self):
        item = SimpleNamespace(
            id=1,
            status=RestoreRecordItem.Status.RUNNING,
            last_progress_snapshot={},
            last_progress_sample={},
            source_path="/restore",
            target_path="/data",
        )
        snapshot_directory = SimpleNamespace(size_bytes=563_000_000)
        lane = _lane_from_item(item, snapshot_directory=snapshot_directory)
        progress = lane["progress"]
        self.assertTrue(progress["bytes_total_known"])
        self.assertEqual(progress["bytes_total"], 563_000_000)
        self.assertFalse(progress["bytes_total_reference"])

    def test_kopia_progress_uses_snapshot_floor_without_ref(self):
        item = SimpleNamespace(
            id=1,
            status=RestoreRecordItem.Status.RUNNING,
            last_progress_snapshot={
                "phase": "kopia_transfer",
                "kopia_phase": "restoring",
                "bytes_done": 9_500_000,
                "bytes_total": 500_000_000,
                "bytes_total_known": True,
            },
            last_progress_sample={},
            source_path="/restore",
            target_path="/data",
        )
        snapshot_directory = SimpleNamespace(size_bytes=563_000_000)
        lane = _lane_from_item(item, snapshot_directory=snapshot_directory)
        progress = lane["progress"]
        self.assertEqual(progress["bytes_total"], 563_000_000)
        self.assertFalse(progress["bytes_total_reference"])

    def test_restore_lane_uses_processed_bytes_not_uploaded(self):
        item = SimpleNamespace(
            id=1,
            status=RestoreRecordItem.Status.RUNNING,
            last_progress_snapshot={
                "phase": "kopia_transfer",
                "kopia_phase": "restoring",
                "processed_bytes": 12_000_000,
                "processed_count": 120,
                "total_count": 5000,
                "speed_bps": 2_000_000,
            },
            last_progress_sample={},
            source_path="/restore",
            target_path="/data",
        )
        snapshot_directory = SimpleNamespace(size_bytes=563_000_000)
        lane = _lane_from_item(item, snapshot_directory=snapshot_directory)
        progress = lane["progress"]
        self.assertEqual(progress["bytes_done"], 12_000_000)
        self.assertEqual(progress["processed_count"], 120)
        self.assertEqual(progress["total_count"], 5000)
