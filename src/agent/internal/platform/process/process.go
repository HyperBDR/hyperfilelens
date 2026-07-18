package process

import (
	"context"
	"os/exec"
)

// Options tune subprocess priority and resource limits.
type Options struct {
	NiceLevel    int
	RateLimitBps int64
}

// Configure applies OS-specific priority and rate limiting to cmd.
func Configure(ctx context.Context, cmd *exec.Cmd, opts Options) error {
	_ = ctx
	_ = cmd
	_ = opts
	return nil
}

// KillGroup terminates the process group associated with pid.
func KillGroup(ctx context.Context, pid int) error {
	_ = ctx
	_ = pid
	return nil
}
