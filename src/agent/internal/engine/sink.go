package engine

import "context"

// ExecutionSink receives progress and optional completion notifications during Run.
type ExecutionSink interface {
	OnProgress(ctx context.Context, progress map[string]any) error
}

// NullSink discards progress updates.
type NullSink struct{}

func (NullSink) OnProgress(context.Context, map[string]any) error { return nil }

// ReporterSink adapts ExecutionSink to the legacy task-id keyed progress shape.
type ReporterSink struct {
	Sink   ExecutionSink
	TaskID string
}

func (r ReporterSink) TaskProgress(ctx context.Context, taskID string, progress map[string]any) error {
	if r.Sink == nil {
		return nil
	}
	if taskID == "" {
		taskID = r.TaskID
	}
	return r.Sink.OnProgress(ctx, progress)
}
