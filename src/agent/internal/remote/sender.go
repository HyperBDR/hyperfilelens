package remote

import (
	"context"
	"sync"

	"hyperfilelens/agent/internal/infra/monitor"
	"hyperfilelens/agent/internal/wire"
)

// Sender asynchronously reports progress and monitor samples upstream.
type Sender struct {
	mu sync.RWMutex
	tr wire.Sender
}

// NewSender returns an uplink reporter.
func NewSender() *Sender {
	return &Sender{}
}

// Bind attaches the active Connector (or any wire.Sender) for uplink sends.
func (s *Sender) Bind(tr wire.Sender) {
	s.mu.Lock()
	s.tr = tr
	s.mu.Unlock()
}

func (s *Sender) sink() wire.Sender {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.tr
}

// SendProgress enqueues a task.progress update for the control plane.
func (s *Sender) SendProgress(ctx context.Context, taskID, jobID, phase string, percent float64, detail map[string]any) error {
	tr := s.sink()
	if tr == nil || taskID == "" {
		return nil
	}
	prog := map[string]any{
		"percent": percent,
		"phase":   phase,
	}
	if jobID != "" {
		prog["job_id"] = jobID
	}
	for k, v := range detail {
		prog[k] = v
	}
	return wire.SendTaskProgress(ctx, tr, taskID, prog)
}

// SendMonitorSample enqueues a host resource sample via heartbeat payload.
func (s *Sender) SendMonitorSample(ctx context.Context, sample monitor.Sample) error {
	tr := s.sink()
	if tr == nil {
		return nil
	}
	return wire.SendHeartbeatWithPayload(ctx, tr, map[string]any{
		"metrics": sample.ToPayload(),
	})
}
