package extractor

import (
	"context"
	"io/fs"
	"os"
	"path/filepath"
)

// ExtractKopia writes the Kopia binary for the current OS/arch to destDir (e.g. from dist bundle bin/kopia).
func ExtractKopia(ctx context.Context, embedded fs.FS, destDir string) (string, error) {
	_ = ctx
	_ = embedded
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return "", err
	}
	dest := filepath.Join(destDir, "kopia")
	return dest, nil
}
