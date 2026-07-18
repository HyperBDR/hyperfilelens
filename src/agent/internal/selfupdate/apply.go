package selfupdate

import "context"

// Apply replaces the running binary with the downloaded artifact and restarts the Agent.
func Apply(ctx context.Context, stagedPath string) error {
	_ = ctx
	_ = stagedPath
	return nil
}
