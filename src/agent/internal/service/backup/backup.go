package backup

import (
	"context"

	"hyperfilelens/agent/internal/platform/kopia"
	"hyperfilelens/agent/internal/platform/process"
)

// Service wraps Kopia snapshot invocations.
type Service struct {
	binary string
}

// NewService returns a backup service using the resolved Kopia binary path.
func NewService(kopiaPath string) (*Service, error) {
	bin, err := kopia.Resolve(kopiaPath)
	if err != nil {
		return nil, err
	}
	return &Service{binary: bin}, nil
}

// Run executes ``kopia`` with the given subcommand arguments.
func (s *Service) Run(ctx context.Context, args []string, env map[string]string) (process.Result, error) {
	return process.Run(ctx, s.binary, args, env, "")
}
