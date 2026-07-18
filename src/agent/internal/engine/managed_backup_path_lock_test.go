package engine

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestManagedBackupPathLockSerializesSameKey(t *testing.T) {
	registry := newManagedBackupPathLockRegistry()
	releaseFirst, err := registry.acquire(context.Background(), "/tmp/repo.config", "/data")
	if err != nil {
		t.Fatal(err)
	}

	acquired := make(chan func(), 1)
	go func() {
		release, acquireErr := registry.acquire(context.Background(), "/tmp/repo.config", "/data")
		if acquireErr == nil {
			acquired <- release
		}
	}()

	select {
	case release := <-acquired:
		release()
		t.Fatal("same repository path lock was acquired concurrently")
	case <-time.After(50 * time.Millisecond):
	}

	releaseFirst()
	select {
	case release := <-acquired:
		release()
	case <-time.After(time.Second):
		t.Fatal("waiting repository path lock was not released")
	}
}

func TestManagedBackupPathLockAllowsDifferentPaths(t *testing.T) {
	registry := newManagedBackupPathLockRegistry()
	releaseFirst, err := registry.acquire(context.Background(), "/tmp/repo.config", "/data")
	if err != nil {
		t.Fatal(err)
	}
	defer releaseFirst()

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	releaseSecond, err := registry.acquire(ctx, "/tmp/repo.config", "/home")
	if err != nil {
		t.Fatalf("different source path should not block: %v", err)
	}
	releaseSecond()
}

func TestManagedBackupPathLockWaitHonorsCancellation(t *testing.T) {
	registry := newManagedBackupPathLockRegistry()
	releaseFirst, err := registry.acquire(context.Background(), "/tmp/repo.config", "/data")
	if err != nil {
		t.Fatal(err)
	}
	defer releaseFirst()

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := registry.acquire(ctx, "/tmp/repo.config", "/data"); !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context cancellation, got %v", err)
	}
}
