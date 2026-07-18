package engine

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestRunLensKsPrepareCreatesDirectory(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "ks-42")
	eng := New(nil)

	status, result, errMsg := eng.runLensKsPrepare(context.Background(), Payload{
		Path: target,
		Extra: map[string]any{
			"workspace_root": root,
		},
	})
	if status != "success" {
		t.Fatalf("status=%q err=%q result=%v", status, errMsg, result)
	}
	info, err := os.Stat(target)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if !info.IsDir() {
		t.Fatalf("expected directory")
	}
}

func TestRunLensKsPrepareRejectsPathOutsideRoot(t *testing.T) {
	root := t.TempDir()
	eng := New(nil)

	status, _, errMsg := eng.runLensKsPrepare(context.Background(), Payload{
		Path: "/tmp/outside",
		Extra: map[string]any{
			"workspace_root": root,
		},
	})
	if status != "failed" {
		t.Fatalf("expected failure, got status=%q", status)
	}
	if errMsg == "" {
		t.Fatal("expected error message")
	}
}
