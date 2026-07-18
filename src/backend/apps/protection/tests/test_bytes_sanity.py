from django.test import SimpleTestCase

from apps.protection.services.progress.bytes_sanity import (
    apply_reference_bytes_total,
    credible_bytes_total,
    monotonic_bytes_total,
)
from apps.protection.services.progress.lane_sampler import apply_speed_and_eta
from apps.protection.services.progress.orchestration_label import backup_orchestration_label_meta


class BytesSanityTests(SimpleTestCase):
    def test_rejects_total_smaller_than_done(self):
        self.assertFalse(credible_bytes_total(bytes_done=6_400_000_000, bytes_total=3))

    def test_monotonic_total_never_below_done(self):
        total = monotonic_bytes_total(
            bytes_done=6_400_000_000,
            bytes_total=3,
            previous_max=7_000_000_000,
        )
        self.assertEqual(total, 7_000_000_000)

    def test_apply_reference_replaces_inflated_estimate(self):
        reference = 2_000_000_000
        total, replaced = apply_reference_bytes_total(
            bytes_total=206_400_000_000,
            reference_bytes_total=reference,
        )
        self.assertTrue(replaced)
        self.assertEqual(total, reference)

    def test_monotonic_allows_decrease_to_reference(self):
        reference = 2_200_000_000
        total = monotonic_bytes_total(
            bytes_done=561_000_000,
            bytes_total=206_400_000_000,
            previous_max=206_400_000_000,
            reference_bytes_total=reference,
        )
        self.assertEqual(total, reference)
        self.assertTrue(credible_bytes_total(bytes_done=561_000_000, bytes_total=total))


class LaneSamplerTests(SimpleTestCase):
    def test_read_only_path_preserves_sample_timestamp(self):
        sample = {
            "counter": 1000,
            "sampled_at": "2026-07-02T10:00:00+00:00",
            "_max_bytes_total": 5000,
        }
        result = apply_speed_and_eta(
            lane={
                "kopia_phase": "uploading",
                "uploaded_bytes": 1000,
                "bytes_done": 1000,
                "bytes_total_known": False,
            },
            sample=sample,
            persist_sample=False,
        )
        self.assertEqual(result["last_sample"]["sampled_at"], sample["sampled_at"])
        self.assertEqual(result["last_sample"]["counter"], 1000)

    def test_eta_prefers_computed_when_kopia_eta_too_short_for_total(self):
        bytes_total = 204 * 1000 * 1000 * 1000
        bytes_done = 28 * 1000 * 1000
        speed_bps = int(2.68 * 1000 * 1000)
        result = apply_speed_and_eta(
            lane={
                "kopia_phase": "uploading",
                "uploaded_bytes": bytes_done,
                "bytes_done": bytes_done,
                "bytes_total": bytes_total,
                "bytes_total_known": True,
                "speed_bps": speed_bps,
                "kopia_eta_seconds": 46,
            },
            sample=None,
            persist_sample=False,
        )
        self.assertEqual(result["eta_source"], "computed")
        remaining = bytes_total - bytes_done
        expected = int(remaining / speed_bps)
        self.assertEqual(result["eta_seconds"], expected)
        self.assertGreater(result["eta_seconds"], 3600)

    def test_eta_keeps_credible_kopia_eta_when_total_unknown(self):
        result = apply_speed_and_eta(
            lane={
                "kopia_phase": "hashing",
                "hashed_bytes": 500_000_000,
                "bytes_done": 500_000_000,
                "bytes_total_known": False,
                "speed_bps": 10_000_000,
                "kopia_eta_seconds": 120,
            },
            sample=None,
            persist_sample=False,
        )
        self.assertEqual(result["eta_source"], "kopia")
        self.assertEqual(result["eta_seconds"], 120)


class OrchestrationLabelMetaTests(SimpleTestCase):
    def test_uploading_label_key(self):
        meta, phase = backup_orchestration_label_meta(
            task_status="running",
            lanes=[{
                "id": "1",
                "name": "/data",
                "status": "running",
                "progress": {
                    "is_transfer": True,
                    "kopia_phase": "uploading",
                    "bytes_done": 1,
                    "bytes_total_known": True,
                    "bytes_total": 10,
                },
            }],
            aggregate={"lanes_done": 0, "lanes_total": 1},
        )
        self.assertEqual(phase, "transferring")
        self.assertEqual(meta["label_key"], "protection.taskProgress.backup.uploading")
