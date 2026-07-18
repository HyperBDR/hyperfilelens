package maintenance

import (
	"context"
	"os"
	"path/filepath"

	"hyperfilelens/agent/internal/platform/kopia"
	"hyperfilelens/agent/internal/platform/process"
)

// Service performs repository maintenance and local housekeeping.
type Service struct {
	binary string
}

// NewService returns a maintenance service using the resolved Kopia binary path.
func NewService(kopiaPath string) (*Service, error) {
	bin, err := kopia.Resolve(kopiaPath)
	if err != nil {
		return nil, err
	}
	return &Service{binary: bin}, nil
}

// RunGC triggers ``kopia maintenance run``.
func (s *Service) RunGC(ctx context.Context, configFile string) (process.Result, error) {
	args := []string{"maintenance", "run", "--full"}
	if configFile != "" {
		args = append([]string{"--config-file=" + configFile}, args...)
	}
	return process.Run(ctx, s.binary, args, nil, "")
}

// RotateLogs is a placeholder for local log rotation (see infra/logging).
func (s *Service) RotateLogs(ctx context.Context, logDir string) error {
	_ = s
	_ = ctx
	_ = logDir
	return nil
}

// CleanCache removes files under cacheDir (non-recursive top-level only).
func (s *Service) CleanCache(ctx context.Context, cacheDir string) error {
	_ = ctx
	if cacheDir == "" {
		return nil
	}
	entries, err := os.ReadDir(cacheDir)
	if err != nil {
		return err
	}
	for _, e := range entries {
		_ = os.RemoveAll(filepath.Join(cacheDir, e.Name()))
	}
	return nil
}
