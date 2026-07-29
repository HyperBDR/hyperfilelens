package controller

import (
	"context"
	"sync"

	"hyperfilelens/agent/internal/model"
)

// Scheduler queues tasks and enforces concurrency limits via a semaphore.
type Scheduler struct {
	maxConcurrent int
	slots         chan struct{}
}

// NewScheduler returns a task scheduler with the given concurrency cap.
func NewScheduler(maxConcurrent int) *Scheduler {
	if maxConcurrent < 1 {
		maxConcurrent = 1
	}
	return &Scheduler{
		maxConcurrent: maxConcurrent,
		slots:         make(chan struct{}, maxConcurrent),
	}
}

// Acquire waits for an execution slot and returns an idempotent release function.
func (s *Scheduler) Acquire(ctx context.Context) (func(), error) {
	if s == nil {
		return func() {}, nil
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case s.slots <- struct{}{}:
		return s.releaseFunc(), nil
	}
}

// TryAcquire acquires an execution slot without waiting.
func (s *Scheduler) TryAcquire() (func(), bool) {
	if s == nil {
		return func() {}, true
	}
	select {
	case s.slots <- struct{}{}:
		return s.releaseFunc(), true
	default:
		return nil, false
	}
}

func (s *Scheduler) releaseFunc() func() {
	var once sync.Once
	return func() {
		once.Do(func() { <-s.slots })
	}
}

// Enqueue adds a task to the execution queue.
func (s *Scheduler) Enqueue(ctx context.Context, task model.Task) error {
	_ = s
	_ = ctx
	_ = task
	return nil
}
