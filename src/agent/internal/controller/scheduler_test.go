package controller

import (
	"context"
	"testing"
	"time"
)

func TestSchedulerEnforcesConcurrencyLimit(t *testing.T) {
	scheduler := NewScheduler(2)
	releaseFirst, ok := scheduler.TryAcquire()
	if !ok {
		t.Fatal("first slot was not acquired")
	}
	releaseSecond, ok := scheduler.TryAcquire()
	if !ok {
		t.Fatal("second slot was not acquired")
	}
	if release, acquired := scheduler.TryAcquire(); acquired {
		release()
		t.Fatal("third slot was acquired above the concurrency limit")
	}

	acquired := make(chan func(), 1)
	go func() {
		release, err := scheduler.Acquire(context.Background())
		if err == nil {
			acquired <- release
		}
	}()
	select {
	case release := <-acquired:
		release()
		t.Fatal("waiting acquire completed before a slot was released")
	case <-time.After(20 * time.Millisecond):
	}

	releaseFirst()
	select {
	case release := <-acquired:
		release()
	case <-time.After(time.Second):
		t.Fatal("waiting acquire did not complete after a slot was released")
	}
	releaseSecond()
}

func TestSchedulerAcquireHonorsContextCancellation(t *testing.T) {
	scheduler := NewScheduler(1)
	release, ok := scheduler.TryAcquire()
	if !ok {
		t.Fatal("slot was not acquired")
	}
	defer release()

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := scheduler.Acquire(ctx); err == nil {
		t.Fatal("expected canceled acquire to fail")
	}
}
