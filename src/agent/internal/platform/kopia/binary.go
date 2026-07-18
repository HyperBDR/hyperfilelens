// Package kopia locates and invokes the host-installed Kopia CLI (not bundled by Agent).
package kopia

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// ErrNotFound means the kopia binary is not on PATH and HFL_KOPIA_PATH is unset/invalid.
var ErrNotFound = errors.New("kopia CLI not found on PATH; set HFL_KOPIA_PATH")

// Resolve returns an absolute path to the kopia binary.
func Resolve(configured string) (string, error) {
	if p := strings.TrimSpace(configured); p != "" {
		if _, err := os.Stat(p); err != nil {
			return "", fmt.Errorf("kopia at %q: %w", p, err)
		}
		return filepath.Clean(p), nil
	}
	path, err := exec.LookPath("kopia")
	if err != nil {
		return "", ErrNotFound
	}
	return filepath.Clean(path), nil
}

// Version runs ``kopia --version`` and returns trimmed stdout.
func Version(ctx context.Context, bin string) (string, error) {
	cmd := exec.CommandContext(ctx, bin, "--version")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}
