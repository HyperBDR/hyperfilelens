package engine

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDeleteManagedRepositoryPathRejectsTraversalAndRoot(t *testing.T) {
	root := t.TempDir()
	if _, _, err := deleteManagedRepositoryPath(context.Background(), root, root); err == nil {
		t.Fatal("expected cleanup root deletion to be rejected")
	}
	outside := filepath.Join(filepath.Dir(root), "outside")
	if _, _, err := deleteManagedRepositoryPath(context.Background(), outside, root); err == nil {
		t.Fatal("expected cleanup outside allowed root to be rejected")
	}
	if _, _, err := deleteManagedRepositoryPath(context.Background(), string(filepath.Separator), ""); err == nil {
		t.Fatal("expected filesystem root deletion to be rejected")
	}
}

func TestDeleteManagedRepositoryPathIsIdempotent(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "hp-repos", "agent-1")
	if err := os.MkdirAll(target, 0o755); err != nil {
		t.Fatal(err)
	}
	if _, existed, err := deleteManagedRepositoryPath(context.Background(), target, root); err != nil || !existed {
		t.Fatalf("first cleanup existed=%v err=%v", existed, err)
	}
	if _, existed, err := deleteManagedRepositoryPath(context.Background(), target, root); err != nil || existed {
		t.Fatalf("second cleanup existed=%v err=%v", existed, err)
	}
}

func TestDeleteManagedRepositoryPathRejectsSymlink(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	link := filepath.Join(root, "hp-repos")
	if err := os.Symlink(outside, link); err != nil {
		t.Skipf("symlink is unavailable: %v", err)
	}
	target := filepath.Join(link, "agent-1")
	if _, _, err := deleteManagedRepositoryPath(context.Background(), target, root); err == nil {
		t.Fatal("expected symbolic link component to be rejected")
	}
}

func TestDeleteManagedRepositoryPathHonorsCancellation(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "hp-repos", "agent-1")
	if err := os.MkdirAll(target, 0o755); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, _, err := deleteManagedRepositoryPath(ctx, target, root); err == nil {
		t.Fatal("expected canceled cleanup to fail")
	}
	if _, err := os.Stat(target); err != nil {
		t.Fatalf("canceled cleanup removed target: %v", err)
	}
}

func TestRemoveRepositoryLocalStateReturnsCountWithoutPaths(t *testing.T) {
	configFile := filepath.Join(t.TempDir(), "repository.config")
	maintenanceFile := strings.TrimSuffix(configFile, filepath.Ext(configFile)) + ".maintenance.config"
	for _, path := range []string{configFile, maintenanceFile} {
		if err := os.WriteFile(path, []byte("test"), 0o600); err != nil {
			t.Fatal(err)
		}
	}

	removed, err := removeRepositoryLocalState(configFile)
	if err != nil {
		t.Fatal(err)
	}
	if removed != 2 {
		t.Fatalf("removed config count = %d, want 2", removed)
	}
}

func TestRedactRepositoryCleanupPaths(t *testing.T) {
	path := filepath.Join(string(filepath.Separator), "sensitive", "repository")
	message := redactRepositoryCleanupPaths("remove "+path+": permission denied", path)
	if strings.Contains(message, path) {
		t.Fatalf("cleanup error leaked path: %q", message)
	}
}
