from django.test import SimpleTestCase

from apps.protection.services.kopia_snapshot_delete import (
    classify_kopia_snapshot_delete_results,
    kopia_snapshot_delete_already_absent,
    normalize_kopia_snapshot_id,
)


class KopiaSnapshotDeleteClassificationTests(SimpleTestCase):
    def test_normalize_rejects_legacy_empty_sentinels(self):
        self.assertEqual(normalize_kopia_snapshot_id(None), "")
        self.assertEqual(normalize_kopia_snapshot_id(" None "), "")
        self.assertEqual(normalize_kopia_snapshot_id("NULL"), "")
        self.assertEqual(normalize_kopia_snapshot_id("abc123"), "abc123")

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

    def test_classify_ignores_legacy_sentinel_results(self):
        deleted, absent, hard = classify_kopia_snapshot_delete_results([
            {
                "status": "failed",
                "kopia_snapshot_id": "None",
                "delete": {"stderr": "invalid object ID"},
            }
        ])
        self.assertEqual(deleted, set())
        self.assertEqual(absent, set())
        self.assertEqual(hard, [])
