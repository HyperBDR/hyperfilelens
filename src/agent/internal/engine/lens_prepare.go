package engine

import (
	"context"
	"os"
	"path/filepath"
	"strings"
)

func (e *Engine) runLensKsPrepare(ctx context.Context, p Payload) (string, map[string]any, string) {
	if err := ctx.Err(); err != nil {
		return "failed", nil, "canceled"
	}

	path := strings.TrimSpace(p.Path)
	workspaceRoot := payloadStringValue(p.Extra["workspace_root"])
	if path == "" {
		return "failed", nil, "path is required"
	}
	if workspaceRoot == "" {
		return "failed", nil, "workspace_root is required"
	}

	cleanPath := filepath.Clean(path)
	cleanRoot := filepath.Clean(strings.TrimRight(workspaceRoot, "/"))
	if cleanPath != cleanRoot && !strings.HasPrefix(cleanPath, cleanRoot+string(os.PathSeparator)) {
		return "failed", nil, "path must be under workspace_root"
	}

	if err := os.MkdirAll(cleanPath, 0o755); err != nil {
		return "failed", nil, err.Error()
	}

	return "success", map[string]any{
		"path":    cleanPath,
		"created": true,
	}, ""
}
