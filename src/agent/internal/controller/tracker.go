package controller

import (
	"context"
	"sync"

	"hyperfilelens/agent/internal/model"
)

type tracked struct {
	task   model.Task
	cancel context.CancelFunc
}

// Tracker maps active tasks to cancellation handles.
type Tracker struct {
	mu    sync.Mutex
	tasks map[string]tracked
}

// NewTracker returns an in-memory active task tracker.
func NewTracker() *Tracker {
	return &Tracker{tasks: make(map[string]tracked)}
}

// Register records a running task and its cancel func.
func (t *Tracker) Register(task model.Task, cancel context.CancelFunc) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.tasks[task.ID] = tracked{task: task, cancel: cancel}
}

// Unregister removes a task from the active set.
func (t *Tracker) Unregister(taskID string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	delete(t.tasks, taskID)
}

// Active returns a snapshot of currently tracked tasks.
func (t *Tracker) Active() []model.Task {
	t.mu.Lock()
	defer t.mu.Unlock()
	out := make([]model.Task, 0, len(t.tasks))
	for _, entry := range t.tasks {
		out = append(out, entry.task)
	}
	return out
}

// Cancel signals cancellation for the task matching id.
func (t *Tracker) Cancel(ctx context.Context, taskID string) error {
	_ = ctx
	t.mu.Lock()
	entry, ok := t.tasks[taskID]
	if ok {
		delete(t.tasks, taskID)
	}
	t.mu.Unlock()
	if !ok {
		return nil
	}
	if entry.cancel != nil {
		entry.cancel()
	}
	return nil
}
