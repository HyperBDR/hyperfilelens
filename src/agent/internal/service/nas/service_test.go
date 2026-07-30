package nas

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"hyperfilelens/agent/internal/platform/vfs"
)

func managedTestMountPoint(t *testing.T, leaf string) string {
	t.Helper()
	dataDir := t.TempDir()
	t.Setenv("HFL_DATA_DIR", dataDir)
	return filepath.Join(vfs.MountSourcesDir(dataDir), leaf)
}

func TestUnmountRemovesEmptyManagedMountDirectory(t *testing.T) {
	mountPoint := managedTestMountPoint(t, "12")
	if err := os.MkdirAll(mountPoint, 0o755); err != nil {
		t.Fatal(err)
	}
	service := NewService()
	if err := service.Unmount(context.Background(), mountPoint); err != nil {
		t.Fatalf("Unmount() error = %v", err)
	}
	if _, err := os.Stat(mountPoint); !os.IsNotExist(err) {
		t.Fatalf("mount directory still exists: %v", err)
	}
	if err := service.Unmount(context.Background(), mountPoint); err != nil {
		t.Fatalf("idempotent Unmount() error = %v", err)
	}
}

func TestUnmountPreservesNonEmptyManagedMountDirectory(t *testing.T) {
	mountPoint := managedTestMountPoint(t, "13")
	if err := os.MkdirAll(mountPoint, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(mountPoint, "retained"), []byte("data"), 0o600); err != nil {
		t.Fatal(err)
	}
	err := NewService().Unmount(context.Background(), mountPoint)
	if err == nil || !strings.Contains(err.Error(), "cleanup mount directory") {
		t.Fatalf("Unmount() error = %v", err)
	}
	if _, statErr := os.Stat(mountPoint); statErr != nil {
		t.Fatalf("non-empty mount directory was removed: %v", statErr)
	}
}

func TestUnmountRejectsManagedSymlink(t *testing.T) {
	mountPoint := managedTestMountPoint(t, "14")
	target := t.TempDir()
	if err := os.MkdirAll(filepath.Dir(mountPoint), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, mountPoint); err != nil {
		t.Fatal(err)
	}
	err := NewService().Unmount(context.Background(), mountPoint)
	if err == nil || !strings.Contains(err.Error(), "symlink") {
		t.Fatalf("Unmount() error = %v", err)
	}
	if _, statErr := os.Stat(target); statErr != nil {
		t.Fatalf("symlink target was affected: %v", statErr)
	}
}
