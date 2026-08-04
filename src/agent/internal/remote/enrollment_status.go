package remote

import (
	"context"
	"time"

	"hyperfilelens/agent/internal/enrollmentclient"
	"hyperfilelens/agent/internal/model"
)

// WaitNodeOnline waits until the control plane confirms a routable WebSocket.
func WaitNodeOnline(
	ctx context.Context,
	cfg *model.AgentConfig,
	nodeID string,
	timeout time.Duration,
) error {
	return enrollmentclient.WaitNodeOnline(ctx, cfg, nodeID, timeout)
}
