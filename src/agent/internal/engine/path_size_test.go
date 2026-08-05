package engine

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestRunPathSizeAcceptsZeroByteFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "empty")
	if err := os.WriteFile(path, nil, 0o600); err != nil {
		t.Fatalf("create empty file: %v", err)
	}

	status, result, message := New(nil).runPathSize(context.Background(), Payload{
		Path:  path,
		Extra: map[string]any{"path_type": "file"},
	})

	if status != "success" {
		t.Fatalf("status = %q, message = %q", status, message)
	}
	if got := result["size_bytes"]; got != uint64(0) {
		t.Fatalf("size_bytes = %#v, want 0", got)
	}
}
