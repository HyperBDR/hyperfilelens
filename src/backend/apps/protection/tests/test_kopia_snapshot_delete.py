from django.test import SimpleTestCase

from apps.protection.services.kopia_snapshot_delete import (
    classify_kopia_snapshot_delete_results,
    kopia_snapshot_delete_already_absent,
)


class KopiaSnapshotDeleteClassificationTests(SimpleTestCase):
    def test_already_absent_detects_no_snapshots_matched(self):
        item = {
            "status": "failed",
            "kopia_snapshot_id": "abc123",
            "delete": {
                "stderr": "error deleting snapshots by root ID abc123: no snapshots matched abc123",
            },
        }
        self.assertTrue(kopia_snapshot_delete_already_absent(item))

    def test_classify_treats_already_absent_as_deleted(self):
        deleted, absent, hard = classify_kopia_snapshot_delete_results([
            {"status": "success", "kopia_snapshot_id": "ok-1"},
            {
                "status": "failed",
                "kopia_snapshot_id": "gone-1",
                "delete": {"stderr": "no snapshots matched gone-1"},
            },
            {
                "status": "failed",
                "kopia_snapshot_id": "bad-1",
                "delete": {"stderr": "permission denied"},
            },
        ])
        self.assertEqual(deleted, {"ok-1"})
        self.assertEqual(absent, {"gone-1"})
        self.assertEqual(len(hard), 1)
