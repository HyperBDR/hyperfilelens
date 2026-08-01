package engine

import (
	"os"
	"path/filepath"
	"testing"

	"hyperfilelens/agent/internal/platform/vfs"
)

func nasRestoreTestPayload(t *testing.T) (Payload, string) {
	t.Helper()
	dataDir := t.TempDir()
	t.Setenv("HFL_DATA_DIR", dataDir)
	mountRoot := vfs.SourceMountPoint(dataDir, 4)
	if err := os.MkdirAll(mountRoot, 0o755); err != nil {
		t.Fatal(err)
	}
	return Payload{Extra: map[string]any{
		"nas": map[string]any{
			"resource_id": 4,
			"protocol":    "nfs",
			"server":      "10.0.0.20",
			"export_path": "/restore",
			"mount_point": vfs.SourceMountPoint(vfs.UnixDataDir(), 4),
		},
	}}, mountRoot
}

func TestResolveNASRestoreTargetUsesRuntimeDataDirectory(t *testing.T) {
	payload, mountRoot := nasRestoreTestPayload(t)

	target, resolvedRoot, err := resolveNASRestoreTarget(
		payload,
		"/restored/data",
	)

	if err != nil {
		t.Fatalf("valid NAS restore target rejected: %v", err)
	}
	if resolvedRoot != mountRoot {
		t.Fatalf("resolved mount root = %q want %q", resolvedRoot, mountRoot)
	}
	want := filepath.Join(mountRoot, "restored", "data")
	if target != want {
		t.Fatalf("resolved target = %q want %q", target, want)
	}
}

func TestValidateNASRestoreTargetRequiresMountContainment(t *testing.T) {
	payload, mountRoot := nasRestoreTestPayload(t)

	if err := validateNASRestoreTarget(
		payload,
		filepath.Join(mountRoot, "restored", "data"),
	); err != nil {
		t.Fatalf("valid NAS restore target rejected: %v", err)
	}
	if err := validateNASRestoreTarget(payload, "/tmp/outside"); err == nil {
		t.Fatal("expected NAS restore target escape rejection")
	}
}

func TestValidateNASRestoreTargetRejectsSymlinkEscape(t *testing.T) {
	payload, mountRoot := nasRestoreTestPayload(t)
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(mountRoot, "escape")); err != nil {
		t.Fatal(err)
	}

	err := validateNASRestoreTarget(
		payload,
		filepath.Join(mountRoot, "escape", "restored.txt"),
	)

	if err == nil {
		t.Fatal("expected NAS restore symlink escape rejection")
	}
}
