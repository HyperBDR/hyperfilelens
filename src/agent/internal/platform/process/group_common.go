package process

import (
	"context"
	"os/exec"
	"sync"
)

func startContextProcessGroupKill(ctx context.Context, cmd *exec.Cmd) func() {
	if ctx == nil {
		return func() {}
	}
	done := make(chan struct{})
	var closeOnce sync.Once
	go func() {
		select {
		case <-ctx.Done():
			if cmd.Process != nil {
				killProcessGroup(cmd.Process)
			}
		case <-done:
		}
	}()
	return func() {
		closeOnce.Do(func() { close(done) })
	}
}
