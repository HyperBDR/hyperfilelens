package wire

import (
	"context"
	"path/filepath"
	"testing"

	"hyperfilelens/agent/internal/controller"
	"hyperfilelens/agent/internal/infra/database"
	"hyperfilelens/agent/internal/model"
)

type captureSender struct {
	frames []any
}

func (s *captureSender) SendJSON(_ context.Context, frame any) error {
	s.frames = append(s.frames, frame)
	return nil
}

func newFinishedTaskHandler(t *testing.T) (*Handler, *database.TaskRepo) {
	t.Helper()
	ctx := t.Context()
	db, err := database.Open(ctx, filepath.Join(t.TempDir(), "agent.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	repo := database.NewTaskRepo(db)
	if err := repo.RecordCommand(ctx, database.RecordInput{TaskID: "task-1", Kind: "backup.run"}); err != nil {
		t.Fatal(err)
	}
	if err := repo.Finish(ctx, "task-1", model.TaskStatusSucceeded, map[string]any{"kopia_snapshot_id": "snap-1"}, ""); err != nil {
		t.Fatal(err)
	}
	return NewHandler(nil, controller.NewTracker(), repo), repo
}

func TestFlushUnreportedWaitsForAckInAckMode(t *testing.T) {
	handler, repo := newFinishedTaskHandler(t)
	handler.SetTaskResultAckEnabled(true)
	sender := &captureSender{}
	if err := handler.FlushUnreportedResults(t.Context(), sender); err != nil {
		t.Fatal(err)
	}
	if len(sender.frames) != 1 {
		t.Fatalf("frames = %d, want 1", len(sender.frames))
	}
	pending, err := repo.ListUnreported(t.Context())
	if err != nil {
		t.Fatal(err)
	}
	if len(pending) != 1 {
		t.Fatalf("pending before ack = %d, want 1", len(pending))
	}
	if err := handler.Handle(
		t.Context(),
		[]byte(`{"type":"task.result.ack","task_id":"task-1"}`),
		sender,
	); err != nil {
		t.Fatal(err)
	}
	pending, err = repo.ListUnreported(t.Context())
	if err != nil {
		t.Fatal(err)
	}
	if len(pending) != 0 {
		t.Fatalf("pending after ack = %d, want 0", len(pending))
	}
}

func TestFlushUnreportedKeepsLegacyMarkOnWrite(t *testing.T) {
	handler, repo := newFinishedTaskHandler(t)
	handler.SetTaskResultAckEnabled(false)
	if err := handler.FlushUnreportedResults(t.Context(), &captureSender{}); err != nil {
		t.Fatal(err)
	}
	pending, err := repo.ListUnreported(t.Context())
	if err != nil {
		t.Fatal(err)
	}
	if len(pending) != 0 {
		t.Fatalf("legacy pending = %d, want 0", len(pending))
	}
}
