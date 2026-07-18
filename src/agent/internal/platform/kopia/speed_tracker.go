package kopia

import (
	"sync"
	"time"
)

const (
	speedMinSampleGap   = 2 * time.Second
	speedMinBps         = int64(100)
	speedEmaAlpha       = 0.35
)

// SpeedTracker computes smoothed upload/hash throughput from byte counter samples.
type SpeedTracker struct {
	mu          sync.Mutex
	lastCounter int64
	lastAt      time.Time
	emaSpeed    float64
	hasSample   bool
}

func (t *SpeedTracker) Observe(counter int64, now time.Time) (speedBps int64, source string) {
	if counter <= 0 {
		return 0, ""
	}
	t.mu.Lock()
	defer t.mu.Unlock()

	if !t.hasSample {
		t.lastCounter = counter
		t.lastAt = now
		t.hasSample = true
		return 0, ""
	}

	if counter < t.lastCounter {
		t.lastCounter = counter
		t.lastAt = now
		t.emaSpeed = 0
		return 0, ""
	}

	if counter == t.lastCounter {
		if t.emaSpeed > 0 {
			return int64(t.emaSpeed), "ema"
		}
		return 0, ""
	}

	deltaT := now.Sub(t.lastAt)
	if deltaT < speedMinSampleGap {
		if t.emaSpeed > 0 {
			return int64(t.emaSpeed), "ema"
		}
		return 0, ""
	}

	instant := float64(counter-t.lastCounter) / deltaT.Seconds()
	if instant < float64(speedMinBps) {
		t.lastCounter = counter
		t.lastAt = now
		if t.emaSpeed > 0 {
			return int64(t.emaSpeed), "ema"
		}
		return 0, ""
	}

	if t.emaSpeed <= 0 {
		t.emaSpeed = instant
	} else {
		t.emaSpeed = speedEmaAlpha*instant + (1-speedEmaAlpha)*t.emaSpeed
	}
	t.lastCounter = counter
	t.lastAt = now
	return int64(t.emaSpeed), "ema"
}

func SpeedCounter(snapshot ProgressSnapshot) int64 {
	switch snapshot.Phase {
	case "uploading":
		if snapshot.UploadedBytes > 0 {
			return snapshot.UploadedBytes
		}
	case "hashing":
		if snapshot.HashedBytes > 0 {
			return snapshot.HashedBytes
		}
	}
	if snapshot.UploadedBytes > 0 {
		return snapshot.UploadedBytes
	}
	return snapshot.HashedBytes
}
