//go:build linux

package engine

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestLensGatewayBrowseRejectsTraversal(t *testing.T) {
	root := t.TempDir()
	status, _, errMsg := New(nil).runLensGatewayBrowse(context.Background(), Payload{
		Path:  root + "/../../etc",
		Extra: map[string]any{"allowed_root": root},
	})
	if status != "failed" || errMsg == "" {
		t.Fatalf("expected traversal rejection, status=%q err=%q", status, errMsg)
	}
}

func TestLensGatewayBrowseRejectsSymlinkEscape(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	link := filepath.Join(root, "escape")
	if err := os.Symlink(outside, link); err != nil {
		t.Fatal(err)
	}
	status, _, errMsg := New(nil).runLensGatewayBrowse(context.Background(), Payload{
		Path:  link,
		Extra: map[string]any{"allowed_root": root},
	})
	if status != "failed" || errMsg == "" {
		t.Fatalf("expected symlink rejection, status=%q err=%q", status, errMsg)
	}
}

func TestLensWorkspaceValidateLocalAcceptsRealDirectory(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "documents")
	if err := os.Mkdir(target, 0o755); err != nil {
		t.Fatal(err)
	}
	status, result, errMsg := New(nil).runLensWorkspaceValidateLocal(
		context.Background(),
		Payload{
			Path:  target,
			Extra: map[string]any{"allowed_root": root},
		},
	)
	if status != "success" {
		t.Fatalf("status=%q err=%q result=%v", status, errMsg, result)
	}
}

func TestLensGatewayBrowseHidesManagedTrash(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, lensWorkspaceTrashDirectory), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(root, "documents"), 0o755); err != nil {
		t.Fatal(err)
	}

	status, result, errMsg := New(nil).runLensGatewayBrowse(
		context.Background(),
		Payload{Path: root, Extra: map[string]any{"allowed_root": root}},
	)
	if status != "success" {
		t.Fatalf("status=%q err=%q result=%v", status, errMsg, result)
	}
	entries, ok := result["entries"].([]map[string]any)
	if !ok || len(entries) != 1 || entries[0]["name"] != "documents" {
		t.Fatalf("reserved trash leaked into browse result: %#v", result["entries"])
	}
}

func TestLensWorkspaceValidateLocalRejectsManagedTrash(t *testing.T) {
	root := t.TempDir()
	trash := filepath.Join(root, lensWorkspaceTrashDirectory)
	if err := os.Mkdir(trash, 0o700); err != nil {
		t.Fatal(err)
	}

	status, _, errMsg := New(nil).runLensWorkspaceValidateLocal(
		context.Background(),
		Payload{Path: trash, Extra: map[string]any{"allowed_root": root}},
	)
	if status != "failed" || errMsg == "" {
		t.Fatalf("expected reserved trash rejection, status=%q err=%q", status, errMsg)
	}
}
