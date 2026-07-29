package wire

import (
	"context"
	"testing"
	"time"

	"hyperfilelens/agent/internal/controller"
)

type channelSender struct {
	frames chan any
}

func (s *channelSender) SendJSON(_ context.Context, frame any) error {
	s.frames <- frame
	return nil
}

func TestPreparedSnapshotWaitsForSchedulerSlot(t *testing.T) {
	scheduler := controller.NewScheduler(1)
	releaseOccupied, ok := scheduler.TryAcquire()
	if !ok {
		t.Fatal("failed to occupy scheduler slot")
	}
	defer releaseOccupied()

	handler := NewHandler(nil, controller.NewTracker(), nil, scheduler)
	sender := &channelSender{frames: make(chan any, 4)}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		handler.runTask(ctx, sender, &TaskCommand{
			TaskID: "queued-snapshot",
			Kind:   "backup.snapshot.create",
		})
		close(done)
	}()

	select {
	case raw := <-sender.frames:
		progress, ok := raw.(TaskProgress)
		if !ok {
			t.Fatalf("first frame type = %T, want TaskProgress", raw)
		}
		if progress.Progress["kopia_phase"] != "waiting_for_snapshot_slot" {
			t.Fatalf("unexpected queued progress: %#v", progress.Progress)
		}
	case <-time.After(time.Second):
		t.Fatal("queued progress was not sent")
	}

	cancel()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("queued snapshot did not stop after cancellation")
	}
}
