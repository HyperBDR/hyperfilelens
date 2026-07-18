package kopia

import "testing"
import "time"

func TestSpeedTrackerObserveRequiresGap(t *testing.T) {
	tracker := SpeedTracker{}
	now := time.Now()
	if speed, source := tracker.Observe(1000, now); speed != 0 || source != "" {
		t.Fatalf("expected no speed on first sample, got %d %q", speed, source)
	}
	speed, source := tracker.Observe(3_000_000, now.Add(3*time.Second))
	if speed <= 0 || source != "ema" {
		t.Fatalf("expected ema speed after gap, got %d %q", speed, source)
	}
}

func TestCredibleBytesTotalRejectsTooSmallTotal(t *testing.T) {
	if credibleBytesTotal(6_400_000_000, 3) {
		t.Fatalf("expected total=3 bytes to be rejected against 6.4GB done")
	}
	if !credibleBytesTotal(500, 600) {
		t.Fatalf("expected credible total when done < total")
	}
}

func TestHumanSizeHasUnitRejectsBareNumber(t *testing.T) {
	if humanSizeHasUnit("3") {
		t.Fatalf("expected bare number to lack unit")
	}
	if !humanSizeHasUnit("3.00 GB") {
		t.Fatalf("expected GB unit to be detected")
	}
}

func TestTransferBytesRejectsBadEstimatedTotal(t *testing.T) {
	done, total, known := transferBytes(ProgressSnapshot{
		Phase:          "uploading",
		UploadedBytes:  6_400_000_000,
		EstimatedBytes: 3,
	})
	if known || total > 0 {
		t.Fatalf("expected unknown total, got total=%d known=%v done=%d", total, known, done)
	}
}
