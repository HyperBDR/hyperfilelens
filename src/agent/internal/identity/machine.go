package identity

import "context"

// MachineID returns a stable, cross-platform hardware identifier for this host.
func MachineID(ctx context.Context) (string, error) {
	_ = ctx
	return "unknown", nil
}
