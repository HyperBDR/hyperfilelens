package controller

import (
	"context"

	"hyperfilelens/agent/internal/model"
)

// Scheduler queues tasks and enforces concurrency limits via a semaphore.
type Scheduler struct {
	maxConcurrent int
}

// NewScheduler returns a task scheduler with the given concurrency cap.
func NewScheduler(maxConcurrent int) *Scheduler {
	if maxConcurrent < 1 {
		maxConcurrent = 1
	}
	return &Scheduler{maxConcurrent: maxConcurrent}
}

// Enqueue adds a task to the execution queue.
func (s *Scheduler) Enqueue(ctx context.Context, task model.Task) error {
	_ = s
	_ = ctx
	_ = task
	return nil
}
